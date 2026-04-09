"""
Unified LLM client abstracting multiple providers behind a single interface.
Supported providers: openai, anthropic, mistral, moonshot (OpenAI-compatible), gemini.
"""

import time
import re
from typing import Optional
from omegaconf import DictConfig


def _call_openai(prompt: str, model_cfg: DictConfig, llm_cfg: DictConfig) -> str:
    """Call OpenAI-compatible API (GPT, O3, Moonshot/Kimi)."""
    from openai import OpenAI

    kwargs = {"api_key": model_cfg.api_key}
    if model_cfg.get("base_url"):
        kwargs["base_url"] = model_cfg.base_url

    client = OpenAI(**kwargs)
    create_kwargs = {
        "model": model_cfg.model_id,
        "messages": [{"role": "user", "content": prompt}],
        "timeout": llm_cfg.request_timeout,
    }
    
    # OpenAI O-series uses reasoning_effort
    if model_cfg.get("reasoning_effort"):
        create_kwargs["reasoning_effort"] = model_cfg.reasoning_effort
        
    response = client.chat.completions.create(**create_kwargs)
    return response.choices[0].message.content


def _call_anthropic(prompt: str, model_cfg: DictConfig, llm_cfg: DictConfig) -> str:
    """Call Anthropic API (Claude Opus)."""
    import anthropic

    client = anthropic.Anthropic(api_key=model_cfg.api_key)
    create_kwargs = {
        "model": model_cfg.model_id,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
        "timeout": llm_cfg.request_timeout,
    }
    
    if model_cfg.get("thinking_budget"):
        create_kwargs["thinking"] = {
            "type": "enabled", 
            "budget_tokens": model_cfg.thinking_budget
        }
        
    response = client.messages.create(**create_kwargs)
    # Anthropic returns a list of content blocks
    return "".join(block.text for block in response.content if block.type == "text")


def _call_mistral(prompt: str, model_cfg: DictConfig, llm_cfg: DictConfig) -> str:
    """Call Mistral API."""
    from mistralai import Mistral

    client = Mistral(api_key=model_cfg.api_key)
    response = client.chat.complete(
        model=model_cfg.model_id,
        messages=[{"role": "user", "content": prompt}],
        timeout_ms=llm_cfg.request_timeout * 1000,
    )
    return response.choices[0].message.content


# Gemini key rotation state
_gemini_key_index = 0


def _call_gemini(prompt: str, model_cfg: DictConfig, llm_cfg: DictConfig) -> str:
    """Call Google Gemini API using the new google-genai SDK. Supports comma-separated API keys with rotation."""
    from google import genai
    from google.genai import types
    global _gemini_key_index

    keys = [k.strip() for k in model_cfg.api_key.split(",") if k.strip()]
    key = keys[_gemini_key_index % len(keys)]

    try:
        client = genai.Client(api_key=key)
        
        config_kwargs = {}
        if model_cfg.get("thinking_budget"):
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=model_cfg.thinking_budget
            )
            
        if config_kwargs:
            config = types.GenerateContentConfig(**config_kwargs)
            response = client.models.generate_content(
                model=model_cfg.model_id,
                contents=prompt,
                config=config,
            )
        else:
            response = client.models.generate_content(
                model=model_cfg.model_id,
                contents=prompt,
            )
            
        return response.text
    except Exception as e:
        error_msg = str(e).lower()
        if any(kw in error_msg for kw in ("rate limit", "quota", "429")):
            _gemini_key_index = (_gemini_key_index + 1) % len(keys)
        raise


# Provider dispatch table
_PROVIDERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "mistral": _call_mistral,
    "moonshot": _call_openai,  # Moonshot uses OpenAI-compatible API
    "gemini": _call_gemini,
}


def generate(prompt: str, model_cfg: DictConfig, llm_cfg: DictConfig) -> str:
    """
    Generate a response from the specified model.

    Args:
        prompt: The full prompt to send.
        model_cfg: Model-specific config (name, provider, api_key, model_id, base_url).
        llm_cfg: General LLM config (max_retries, retry_delay, request_timeout).

    Returns:
        The model's text response.

    Raises:
        RuntimeError if all retries are exhausted.
    """
    provider = model_cfg.provider
    if provider not in _PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}. Supported: {list(_PROVIDERS.keys())}")

    call_fn = _PROVIDERS[provider]
    last_error: Optional[Exception] = None

    for attempt in range(1, llm_cfg.max_retries + 1):
        try:
            return call_fn(prompt, model_cfg, llm_cfg)
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()

            # Check for rate-limit / quota errors
            if any(kw in error_msg for kw in ("rate limit", "quota", "429", "too many")):
                wait = llm_cfg.retry_delay * attempt
                print(f"  [Rate limit] {model_cfg.name} attempt {attempt}/{llm_cfg.max_retries}. "
                      f"Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [Error] {model_cfg.name} attempt {attempt}/{llm_cfg.max_retries}: {e}")
                if attempt < llm_cfg.max_retries:
                    time.sleep(llm_cfg.retry_delay)
                else:
                    break

    raise RuntimeError(
        f"All {llm_cfg.max_retries} retries exhausted for {model_cfg.name}: {last_error}"
    )


def extract_code(response: str) -> str:
    """Extract C++ code from a model response."""
    # Try ```cpp block first
    match = re.search(r"```cpp\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fall back to any code block
    match = re.search(r"```\w*\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()

    return "No C++ code block found in the response."
