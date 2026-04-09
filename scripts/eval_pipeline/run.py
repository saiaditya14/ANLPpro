#!/usr/bin/env python3
"""
Main evaluation runner.

Two-phase pipeline:
  Phase 1 (Generate): For each active model × problem × enabled test,
           generate solutions and save to readable YAML files.
  Phase 2 (Submit):   If enabled, read saved results and submit code to Codeforces.

Usage:
    # Run all models, all tests, generate only:
    python run.py codeforces.submit_solutions=false

    # Run all models, all tests, generate + submit:
    python run.py

    # Override active models:
    python run.py active_models="[gpt-5.4,o3]"

    # Disable some tests:
    python run.py tests.fudged_samples.enabled=false tests.semantic_perturbation.enabled=false

    # Change pass@k value:
    python run.py tests.k=5

    # Change submit timeout:
    python run.py codeforces.submit_timeout=60
"""

import json
import os
import sys
import time
import yaml
from pathlib import Path

import hydra
from omegaconf import DictConfig, OmegaConf
from dotenv import load_dotenv

# Ensure the script's directory is on the path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import llm_client
import test_runner
import problem_loader
import cf_submit

load_dotenv()


def get_active_model_configs(cfg: DictConfig):
    """Resolve active_models list to actual model config objects."""
    active_names = list(cfg.active_models)
    all_flag = "all" in [n.lower() for n in active_names]

    model_map = {m.name: m for m in cfg.models}

    if all_flag:
        return list(cfg.models)

    selected = []
    for name in active_names:
        if name in model_map:
            selected.append(model_map[name])
        else:
            print(f"  [WARN] Model '{name}' not found in config. Available: {list(model_map.keys())}")
    return selected


# ---------------------------------------------------------------------------
#  Phase 1: Generate solutions and save readable results
# ---------------------------------------------------------------------------

def run_tests_for_problem(
    problem: dict,
    model_cfg: DictConfig,
    cfg: DictConfig,
) -> dict:
    """
    Run all enabled tests for a single problem with a single model.
    Returns a result dict (no submission happens here).
    """
    statement = problem["statement"]
    prompt_prefix = cfg.prompt
    llm_cfg = cfg.llm
    tests_cfg = cfg.tests
    k = tests_cfg.k

    result = {
        "contestId": problem["contestId"],
        "problemIndex": problem["problemIndex"],
        "problemName": problem.get("problemName", "NA"),
        "model": model_cfg.name,
        "solutions": {},
    }

    # 1. pass@k with samples (original statement)
    if tests_cfg.with_samples.enabled:
        print(f"    [pass@{k} with_samples]")
        solutions = test_runner.run_with_samples(
            statement, model_cfg, llm_cfg, prompt_prefix, k=k,
        )
        result["solutions"]["with_samples"] = solutions

    # 2. pass@k without samples
    if tests_cfg.without_samples.enabled:
        print(f"    [pass@{k} without_samples]")
        sol = test_runner.run_without_samples(
            statement, model_cfg, llm_cfg, prompt_prefix, k=k,
        )
        result["solutions"]["without_samples"] = sol

    # 3. pass@k with fudged/wrong samples
    if tests_cfg.fudged_samples.enabled:
        print(f"    [pass@{k} fudged_samples]")
        sol = test_runner.run_fudged_samples(
            statement, model_cfg, llm_cfg, prompt_prefix, k=k,
        )
        result["solutions"]["fudged_samples"] = sol

    # 4. semantic_perturbation
    if tests_cfg.semantic_perturbation.enabled:
        n = tests_cfg.semantic_perturbation.num_variations
        print(f"    [semantic_perturbation] ({n} variations)")
        sols = test_runner.run_semantic_perturbation(
            statement, model_cfg, llm_cfg, prompt_prefix, num_variations=n,
        )
        result["solutions"]["semantic_perturbation"] = sols

    return result


def save_result(result: dict, results_dir: str):
    """
    Save a single problem result as both:
      - YAML (human-readable, for inspection)
      - JSON (machine-readable, for submission phase)
    """
    model_name = result["model"]
    problem_id = f"{result['contestId']}{result['problemIndex']}"

    model_dir = os.path.join(results_dir, model_name)
    os.makedirs(model_dir, exist_ok=True)

    # --- Save JSON (full data, used by submit phase) ---
    json_path = os.path.join(model_dir, f"{problem_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # --- Save readable YAML summary (code only, easy to scan) ---
    summary = _build_readable_summary(result)
    yaml_path = os.path.join(model_dir, f"{problem_id}.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(summary, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=120)

    print(f"    ✓ Saved to {yaml_path}")


def _build_readable_summary(result: dict) -> dict:
    """Build a concise, human-readable summary of results."""
    summary = {
        "problem": f"{result['contestId']}{result['problemIndex']}",
        "name": result.get("problemName", "NA"),
        "model": result["model"],
        "tests": {},
    }

    solutions = result.get("solutions", {})

    # with_samples: list of attempts
    if "with_samples" in solutions:
        attempts = solutions["with_samples"]
        summary["tests"]["with_samples"] = [
            {
                "attempt": a["attempt"],
                "code": a.get("code", ""),
            }
            for a in attempts
        ]

    # without_samples / fudged_samples: dict with attempts list
    for key in ("without_samples", "fudged_samples"):
        if key in solutions:
            sol = solutions[key]
            attempts = sol.get("attempts", [])
            summary["tests"][key] = [
                {
                    "attempt": a["attempt"],
                    "code": a.get("code", ""),
                }
                for a in attempts
            ]

    # semantic_perturbation: list of variations
    if "semantic_perturbation" in solutions:
        summary["tests"]["semantic_perturbation"] = [
            {
                "variation": s["variation"],
                "code": s.get("code", ""),
            }
            for s in solutions["semantic_perturbation"]
        ]

    return summary


# ---------------------------------------------------------------------------
#  Phase 2: Submit saved results to Codeforces
# ---------------------------------------------------------------------------

def _collect_codes_from_result(result: dict) -> list:
    """
    Extract all submittable (contestId, index, code) tuples from a result dict.
    We submit the *last* attempt from each pass@k scenario,
    and every semantic perturbation variation.
    """
    cid = result["contestId"]
    pidx = result["problemIndex"]
    solutions = result.get("solutions", {})
    codes = []

    # For pass@k scenarios, submit last attempt
    for key in ("with_samples", "without_samples", "fudged_samples"):
        if key not in solutions:
            continue
        sol = solutions[key]
        # with_samples is a list directly; others have an "attempts" key
        attempts = sol if isinstance(sol, list) else sol.get("attempts", [])
        if attempts:
            last = attempts[-1]
            code = last.get("code", "")
            if code and "No C++ code block found" not in code:
                codes.append((cid, pidx, code, f"{key}@{len(attempts)}"))

    # Semantic perturbation: submit each variation
    if "semantic_perturbation" in solutions:
        for s in solutions["semantic_perturbation"]:
            code = s.get("code", "")
            if code and "No C++ code block found" not in code:
                codes.append((cid, pidx, code, f"semantic_v{s['variation']}"))

    return codes


def submit_from_results(results_dir: str, cfg: DictConfig):
    """
    Phase 2: Walk through saved JSON results and submit all code to CF.
    """
    print(f"\n{'=' * 70}")
    print("  Phase 2: Submitting solutions to Codeforces")
    print(f"{'=' * 70}")

    submitted = 0
    failed = 0

    for model_dir in sorted(Path(results_dir).iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        print(f"\n  Model: {model_name}")

        for json_file in sorted(model_dir.glob("*.json")):
            with open(json_file, "r", encoding="utf-8") as f:
                result = json.load(f)

            codes = _collect_codes_from_result(result)
            if not codes:
                continue

            pid = f"{result['contestId']}{result['problemIndex']}"
            for cid, pidx, code, label in codes:
                print(f"    Submitting {pid} [{label}]...")
                ok = cf_submit.submit_code_for_problem(cid, pidx, code, cfg)
                if ok:
                    submitted += 1
                else:
                    failed += 1

    print(f"\n  Submission complete: {submitted} submitted, {failed} failed")


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    print("=" * 70)
    print("  Multi-Model Codeforces Evaluation Pipeline")
    print("=" * 70)

    # Resolve paths relative to original cwd (Hydra changes cwd)
    original_cwd = hydra.utils.get_original_cwd()
    os.environ["HYDRA_ORIG_CWD"] = original_cwd

    results_dir = os.path.join(original_cwd, cfg.output.results_dir)
    os.makedirs(results_dir, exist_ok=True)

    # Print active config summary
    active_models = get_active_model_configs(cfg)
    print(f"\nActive models: {[m.name for m in active_models]}")
    print(f"Tests enabled (k={cfg.tests.k}):")
    print(f"  pass@{cfg.tests.k} with_samples: {cfg.tests.with_samples.enabled}")
    print(f"  pass@{cfg.tests.k} without_samples: {cfg.tests.without_samples.enabled}")
    print(f"  pass@{cfg.tests.k} fudged_samples: {cfg.tests.fudged_samples.enabled}")
    print(f"  semantic_perturbation (n={cfg.tests.semantic_perturbation.num_variations}): "
          f"{cfg.tests.semantic_perturbation.enabled}")
    print(f"CF submission: {cfg.codeforces.submit_solutions}")
    print(f"  timeout={cfg.codeforces.submit_timeout}s, "
          f"delay={cfg.codeforces.delay_between_submits}s")
    print()

    # ---- Phase 1: Generate & Save ----
    print(f"{'=' * 70}")
    print("  Phase 1: Generating solutions")
    print(f"{'=' * 70}")

    problems = problem_loader.load_and_fetch_problems(cfg)
    if not problems:
        print("No problems loaded. Exiting.")
        return

    total_work = len(active_models) * len(problems)
    completed = 0

    for model_cfg in active_models:
        print(f"\n{'=' * 70}")
        print(f"  Model: {model_cfg.name} ({model_cfg.provider}/{model_cfg.model_id})")
        print(f"{'=' * 70}")

        for idx, problem in enumerate(problems, 1):
            completed += 1
            pid = f"{problem['contestId']}{problem['problemIndex']}"
            print(f"\n  [{completed}/{total_work}] Problem {pid} "
                  f"({problem.get('problemName', 'NA')})")

            # Skip if result already exists
            result_path = os.path.join(results_dir, model_cfg.name, f"{pid}.json")
            if os.path.exists(result_path):
                print(f"    ⏭ Already processed, skipping")
                continue

            try:
                result = run_tests_for_problem(problem, model_cfg, cfg)
                save_result(result, results_dir)
            except Exception as e:
                print(f"    ✗ Fatal error on {pid}: {e}")
                continue

    print(f"\n{'=' * 70}")
    print(f"  Phase 1 complete! Results saved to {results_dir}/")
    print(f"{'=' * 70}")

    # ---- Phase 2: Submit to CF (if enabled) ----
    if cfg.codeforces.submit_solutions:
        submit_from_results(results_dir, cfg)
    else:
        print(f"\n  CF submission disabled. To submit later, re-run with "
              f"codeforces.submit_solutions=true")

    print(f"\n{'=' * 70}")
    print(f"  Pipeline complete!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
