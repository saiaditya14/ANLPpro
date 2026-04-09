"""
Test runner implementing each evaluation test type.
All three sample scenarios (with/without/fudged) use pass@k with iterative feedback.
Semantic perturbation generates rephrasings then solves each.
"""

import re
from typing import List, Dict, Any
from omegaconf import DictConfig
import llm_client


def remove_sample_cases(problem_statement: str) -> str:
    """Remove everything after 'Example' or 'Input' sections."""
    patterns = [
        r'\nExample\s*\n\s*Input',
        r'\nExamples\s*\n\s*Input',
        r'\nInput\s*\n',
        r'\nSample Input',
    ]
    for pattern in patterns:
        match = re.search(pattern, problem_statement, re.IGNORECASE)
        if match:
            return problem_statement[:match.start()].strip()
    return problem_statement


def fudge_sample_cases(problem_statement: str) -> str:
    """Modify sample test cases with slightly different values."""
    parts = problem_statement.split('\n')
    modified_parts = []
    in_example = False

    for line in parts:
        if re.search(r'Example|Input|Output', line, re.IGNORECASE):
            in_example = True

        if in_example and re.search(r'\d+', line):
            def modify_number(match):
                num = int(match.group())
                return str(num + (1 if num % 2 == 0 else -1))
            line = re.sub(r'\b\d+\b', modify_number, line)

        modified_parts.append(line)

    return '\n'.join(modified_parts)


def _pass_at_k(
    problem_statement: str,
    model_cfg: DictConfig,
    llm_cfg: DictConfig,
    prompt_prefix: str,
    k: int,
    label: str = "",
) -> List[Dict[str, Any]]:
    """
    Core pass@k: generate k solutions with iterative failure feedback.

    Returns list of dicts with keys: attempt, full_response, code.
    """
    tag = f" [{label}]" if label else ""
    results = []
    previous_code = ""

    for i in range(k):
        context = ""
        if i > 0 and previous_code:
            context = (
                f"Your previous solution failed. Here is the code you generated:\n\n"
                f"```cpp\n{previous_code}\n```\n\n"
                f"Please analyze it and provide a different, corrected solution."
            )
        elif i > 0:
            context = f"Previous attempt {i} failed. Try a different approach."

        full_prompt = (
            f"{context}\n\n{prompt_prefix}{problem_statement}"
            if context
            else f"{prompt_prefix}{problem_statement}"
        )

        print(f"      pass@{k}{tag} attempt {i + 1}/{k}...")
        try:
            response = llm_client.generate(full_prompt, model_cfg, llm_cfg)
            code = llm_client.extract_code(response)
            previous_code = code
        except Exception as e:
            print(f"      ✗ Error on attempt {i + 1}: {e}")
            response = f"Error: {e}"
            code = ""

        results.append({
            "attempt": i + 1,
            "full_response": response,
            "code": code,
        })

    return results


def run_with_samples(
    problem_statement: str,
    model_cfg: DictConfig,
    llm_cfg: DictConfig,
    prompt_prefix: str,
    k: int = 3,
) -> List[Dict[str, Any]]:
    """pass@k with the original problem statement (samples included)."""
    return _pass_at_k(problem_statement, model_cfg, llm_cfg, prompt_prefix, k, label="with_samples")


def run_without_samples(
    problem_statement: str,
    model_cfg: DictConfig,
    llm_cfg: DictConfig,
    prompt_prefix: str,
    k: int = 3,
) -> Dict[str, Any]:
    """pass@k with sample test cases stripped."""
    stripped = remove_sample_cases(problem_statement)
    attempts = _pass_at_k(stripped, model_cfg, llm_cfg, prompt_prefix, k, label="without_samples")
    return {
        "modified_statement": stripped,
        "attempts": attempts,
    }


def run_fudged_samples(
    problem_statement: str,
    model_cfg: DictConfig,
    llm_cfg: DictConfig,
    prompt_prefix: str,
    k: int = 3,
) -> Dict[str, Any]:
    """pass@k with fudged (wrong) sample test cases."""
    fudged = fudge_sample_cases(problem_statement)
    attempts = _pass_at_k(fudged, model_cfg, llm_cfg, prompt_prefix, k, label="fudged_samples")
    return {
        "modified_statement": fudged,
        "attempts": attempts,
    }


def run_semantic_perturbation(
    problem_statement: str,
    model_cfg: DictConfig,
    llm_cfg: DictConfig,
    prompt_prefix: str,
    num_variations: int = 3,
) -> List[Dict[str, Any]]:
    """
    Generate semantically-equivalent rephrasings of the problem, then solve each.

    Uses the same model to rephrase and then solve.
    Returns list of dicts with keys: variation, perturbed_statement, full_response, code.
    """
    # Step 1: Generate rephrasings
    rephrase_prompt = (
        f"Rephrase the following competitive programming problem statement in "
        f"{num_variations} different ways.\n"
        f"Each variation should:\n"
        f"- Mean exactly the same thing\n"
        f"- Have the same constraints and requirements\n"
        f"- Lead to the same solution approach\n"
        f"- Use different wording and sentence structure\n\n"
        f"Return ONLY the {num_variations} variations separated by "
        f"\"===VARIATION===\" markers.\n\n"
        f"Problem:\n{problem_statement}"
    )

    print(f"      Generating {num_variations} semantic perturbations...")
    try:
        rephrase_response = llm_client.generate(rephrase_prompt, model_cfg, llm_cfg)
        variations = [v.strip() for v in rephrase_response.split("===VARIATION===") if v.strip()]
        variations = variations[:num_variations]
    except Exception as e:
        print(f"      ✗ Error generating perturbations: {e}")
        variations = [problem_statement]

    # Step 2: Solve each variation
    results = []
    for i, variation in enumerate(variations, 1):
        print(f"      Solving semantic variation {i}/{len(variations)}...")
        try:
            response = llm_client.generate(f"{prompt_prefix}{variation}", model_cfg, llm_cfg)
            code = llm_client.extract_code(response)
        except Exception as e:
            print(f"      ✗ Error solving variation {i}: {e}")
            response = f"Error: {e}"
            code = ""

        results.append({
            "variation": i,
            "perturbed_statement": variation,
            "full_response": response,
            "code": code,
        })

    return results
