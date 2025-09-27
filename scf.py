#!/usr/bin/env python3
"""
gemini_batch_screenshots_to_cpp_v2.py

Robust batch sender for screenshots -> Gemini, saving full model output and code.

Usage:
    pip install --upgrade google-genai pillow tqdm
    export GENAI_API_KEY="..."    # or set in PowerShell: $env:GENAI_API_KEY="..."
    python gemini_batch_screenshots_to_cpp_v2.py

Notes:
 - Set MODEL to a model you have access to (e.g. "gemini-2.5-pro" or "gemini-1.5").
 - Adjust MAX_OUTPUT_TOKENS if your account supports larger outputs.
"""
from __future__ import annotations
import os
import sys
import time
import base64
import json
import re
from pathlib import Path
from io import BytesIO
from typing import Optional, List

# Third-party
try:
    from PIL import Image
except Exception:
    print("Install pillow: pip install pillow")
    raise
try:
    from tqdm import tqdm
except Exception:
    print("Install tqdm: pip install tqdm")
    raise

# Try importing google genai SDK
try:
    from google import genai
except Exception as e:
    print("Install google-genai (or python-genai) SDK and ensure it's importable.")
    print("pip install --upgrade google-genai")
    raise

# -----------------------
# Config
# -----------------------
MODEL = "gemini-2.5-pro"           # change to a model you have access to
SCREENSHOTS_DIR = Path("screenshots2")
OUTPUT_DIR = Path("outputs")
PROMPT = (
    "Hey is this image enough to try and solve this problem i.e could you extract all relevant details? "
    "If you have all the details come up with a logic to solve this then give me full c++ code that solves it"
)
FOLLOWUP_PROMPT = "please continue thinking and give me final c++ file"
MAX_FOLLOWUPS = 4
MAX_OUTPUT_TOKENS = 8192         # request a lot so model can finish; change if your account allows more
TEMPERATURE = 0.0
RETRY_MAX = 3
RETRY_BACKOFF_BASE = 2.0

# Heuristics for completeness
MIN_CODE_LINES_FOR_COMPLETE = 10

# -----------------------
# Helpers
# -----------------------
def image_to_base64(img_path: Path) -> str:
    img = Image.open(img_path).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")

def save_text_file(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def extract_code_blocks(text: str) -> List[str]:
    blocks = []
    # fenced code blocks
    fenced = re.findall(r"```(?:cpp|c\+\+|cpp)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    for b in fenced:
        blocks.append(b.strip())
    if blocks:
        return blocks
    # tilde fences
    fenced2 = re.findall(r"~~~(?:cpp|c\+\+)?\s*\n(.*?)~~~", text, flags=re.DOTALL | re.IGNORECASE)
    for b in fenced2:
        blocks.append(b.strip())
    if blocks:
        return blocks
    # heuristic contiguous lines with C++ tokens
    lines = text.splitlines()
    cur = []
    candidates = []
    for ln in lines:
        if re.search(r"\b(int|long|vector|string|scanf|cout|printf|std::|#include|using namespace|return|main)\b", ln):
            cur.append(ln)
        else:
            if len(cur) >= 2:
                candidates.append("\n".join(cur))
            cur = []
    if cur and len(cur) >= 2:
        candidates.append("\n".join(cur))
    blocks.extend([c.strip() for c in candidates])
    return blocks

def looks_complete_cpp(code: str) -> bool:
    if not code:
        return False
    lines = [l for l in code.splitlines() if l.strip()]
    if len(lines) >= MIN_CODE_LINES_FOR_COMPLETE:
        return True
    if re.search(r"\bint\s+main\s*\(", code):
        if "return 0;" in code or code.strip().endswith("}"):
            return True
    if code.count("{") > 0 and code.count("{") == code.count("}"):
        return True
    return False

# -----------------------
# GenAI client wrapper
# -----------------------
def build_client() -> genai.Client:
    key = os.environ.get("GENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if key:
        return genai.Client(api_key=key)
    # fallback: ADC (Vertex / Google credentials) if available
    return genai.Client()

def assemble_text_from_response(resp) -> str:
    """
    Try to extract textual content from SDK response objects across versions.
    Fallback to str(resp).
    """
    try:
        # Some SDKs: resp.candidates[0].content.parts -> each part has .text
        if hasattr(resp, "candidates") and len(resp.candidates) > 0:
            cand = resp.candidates[0]
            # new style: cand.content.parts
            if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                parts = cand.content.parts
                out = ""
                for p in parts:
                    # p may be objects or dicts
                    if hasattr(p, "text"):
                        out += p.text
                    elif isinstance(p, dict) and "text" in p:
                        out += p["text"]
                    else:
                        out += str(p)
                return out
            # older style: cand.text
            if hasattr(cand, "text"):
                return cand.text
        # some SDKs expose resp.text
        if hasattr(resp, "text") and isinstance(resp.text, str):
            return resp.text
    except Exception:
        pass
    # fallback: dump as JSON-able if possible
    try:
        return json.dumps(resp.__dict__, default=str, indent=2)
    except Exception:
        return str(resp)

def call_model_with_image(client: genai.Client, model: str, prompt_text: str, image_b64: str, max_output_tokens: int) -> object:
    """
    Send a multimodal request. Try the high-level pattern first, then fallback to inline base64 payload.
    Returns the raw SDK response object.
    """
    # First attempt: high-level API where SDK accepts a list of contents including prompt and image
    try:
        # many SDKs accept contents as list; also allow max_output_tokens and temperature
        resp = client.models.generate_content(
            model=model,
            contents=[prompt_text, {"type": "image", "image": {"mime_type": "image/png", "data": image_b64}}],
            max_output_tokens=max_output_tokens,
            temperature=TEMPERATURE,
        )
        return resp
    except Exception as e_high:
        # fallback attempt: try text + raw image (some SDK versions accept PIL image directly)
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[prompt_text, image_b64],
                max_output_tokens=max_output_tokens,
                temperature=TEMPERATURE,
            )
            return resp
        except Exception as e_mid:
            # last fallback: use older 'generate' or 'predict' style if present
            try:
                if hasattr(client, "generate") or hasattr(client, "predict"):
                    # attempt to call 'generate' with a dict-like payload
                    payload = {
                        "model": model,
                        "prompt": prompt_text,
                        "image": {"mime_type": "image/png", "data": image_b64},
                        "max_output_tokens": max_output_tokens,
                    }
                    if hasattr(client, "generate"):
                        return client.generate(**payload)
                    else:
                        return client.predict(**payload)
            except Exception as e_low:
                raise RuntimeError(f"All model call attempts failed: {e_high}; {e_mid}; {e_low}")
    # if we reach here, raise
    raise RuntimeError("Model call failed in all attempts")

# -----------------------
# Main processing loop
# -----------------------
def process_image_file(client: genai.Client, model: str, img_path: Path, out_dir: Path):
    name = img_path.stem
    raw_out = out_dir / f"{name}.raw.txt"
    txt_out = out_dir / f"{name}.response.txt"
    cpp_out = out_dir / f"{name}.cpp"

    image_b64 = image_to_base64(img_path)

    accumulated_response_text = ""
    turn = 0
    completed = False

    while turn < (1 + MAX_FOLLOWUPS) and not completed:
        turn += 1
        if turn == 1:
            prompt = PROMPT
        else:
            prompt = FOLLOWUP_PROMPT

        # try call with retries
        attempt = 0
        last_exception = None
        while attempt < RETRY_MAX:
            attempt += 1
            try:
                resp = call_model_with_image(client, model, prompt, image_b64, MAX_OUTPUT_TOKENS)
                break
            except Exception as e:
                last_exception = e
                wait = RETRY_BACKOFF_BASE ** attempt
                print(f"[{name}] model call failed (attempt {attempt}/{RETRY_MAX}): {e}. backoff {wait}s")
                time.sleep(wait)
        else:
            # all retries failed
            errtxt = f"[{name}] ERROR: model call failed after {RETRY_MAX} attempts: {last_exception}\n"
            accumulated_response_text += "\n" + errtxt
            save_text_file(raw_out, errtxt)
            save_text_file(txt_out, accumulated_response_text)
            return

        # assemble textual reply
        text = assemble_text_from_response(resp)
        # save raw SDK representation too
        try:
            # try to save JSON-ish representation if possible
            raw_str = ""
            try:
                raw_str = json.dumps(resp.__dict__, default=str, indent=2)
            except Exception:
                raw_str = str(resp)
        except Exception:
            raw_str = str(resp)
        save_text_file(raw_out, raw_str)

        # append to accumulated conversation
        accumulated_response_text += f"\n\n--- turn {turn} ---\n"
        accumulated_response_text += text
        save_text_file(txt_out, accumulated_response_text)

        # extract code blocks
        blocks = extract_code_blocks(text)
        if not blocks:
            # also try extracting from accumulated text
            blocks = extract_code_blocks(accumulated_response_text)

        if blocks:
            # choose largest block by line count
            blocks_sorted = sorted(blocks, key=lambda b: len([l for l in b.splitlines() if l.strip()]), reverse=True)
            candidate = blocks_sorted[0].strip()
            save_text_file(cpp_out, candidate)
            if looks_complete_cpp(candidate):
                print(f"[{name}] Received apparently complete C++ code on turn {turn}.")
                completed = True
                break
            else:
                print(f"[{name}] Found code on turn {turn} but it appears incomplete; requesting continuation.")
                # continue loop to send followup
        else:
            print(f"[{name}] No code block found on turn {turn}; will follow up if allowed.")

        # small polite pause
        time.sleep(1.0)

    # final status
    if not cpp_out.exists():
        print(f"[{name}] No C++ code saved (check {txt_out}).")
    else:
        print(f"[{name}] Done. Saved response: {txt_out}, raw: {raw_out}, code: {cpp_out}")

def main():
    client = build_client()
    out_dir = OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if not SCREENSHOTS_DIR.exists():
        print("Screenshots folder not found:", SCREENSHOTS_DIR.resolve())
        sys.exit(1)

    img_paths = sorted([p for p in SCREENSHOTS_DIR.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])
    if not img_paths:
        print("No images found in", SCREENSHOTS_DIR)
        sys.exit(0)

    print("Using model:", MODEL)
    for img in tqdm(img_paths, desc="Images"):
        try:
            process_image_file(client, MODEL, img, out_dir)
            # small sleep between images to avoid hitting rate limits
            time.sleep(1.0)
        except KeyboardInterrupt:
            print("Interrupted by user")
            break
        except Exception as e:
            print(f"Error processing {img}: {e}")

if __name__ == "__main__":
    main()
