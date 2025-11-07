#!/usr/bin/env python3
"""
Generate solution variations for non-accepted problems.
Metrics:
- pass@5: Generate 5 solutions assuming each fails
- without_samples: Remove sample test cases from problem statement
- fudged_samples: Modify sample test cases
- semantic_perturbation: Rephrase problem statement semantically
"""

import json
import yaml
import time
import hydra
from omegaconf import DictConfig
import google.generativeai as genai
import re
import os
import random
from typing import Dict, List, Tuple
from problems import get_problem_statement, parse_problem_statement, extract_code, get_api_keys

# Global variable to track current API key index
current_api_key_index = 0


def acquire_lock(lock_file):
    """Acquire a lock using a lock file."""
    while True:
        try:
            # Attempt to create the lock file exclusively
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return
        except FileExistsError:
            # Lock is held by another process, wait and retry
            time.sleep(random.uniform(0.1, 0.5))

def release_lock(lock_file):
    """Release the lock by deleting the lock file."""
    try:
        os.remove(lock_file)
    except OSError as e:
        # Log if the lock file doesn't exist, but don't crash
        print(f"Warning: Could not release lock {lock_file}. Reason: {e}")
    except OSError:
        pass



def remove_sample_cases(problem_statement: str) -> str:
    """Remove everything after 'Example' or 'Input' sections."""
    # Find the start of examples section
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
    # Find numbers in the examples section and modify them slightly
    parts = problem_statement.split('\n')
    modified_parts = []
    in_example = False
    
    for line in parts:
        if re.search(r'Example|Input|Output', line, re.IGNORECASE):
            in_example = True
        
        if in_example and re.search(r'\d+', line):
            # Replace numbers with slightly modified versions
            def modify_number(match):
                num = int(match.group())
                # Add or subtract 1-2 randomly
                return str(num + (1 if num % 2 == 0 else -1))
            
            line = re.sub(r'\b\d+\b', modify_number, line)
        
        modified_parts.append(line)
    
    return '\n'.join(modified_parts)


def generate_semantic_perturbations(problem_statement: str, cfg: DictConfig, num_variations: int = 3) -> List[str]:
    """Generate semantically equivalent variations of the problem statement."""
    global current_api_key_index
    
    api_keys = get_api_keys(cfg)
    max_attempts = len(api_keys)
    
    prompt = f"""Rephrase the following competitive programming problem statement in {num_variations} different ways. 
Each variation should:
- Mean exactly the same thing
- Have the same constraints and requirements
- Lead to the same solution approach
- Use different wording and sentence structure

Return ONLY the {num_variations} variations separated by "===VARIATION===" markers.

Problem:
{problem_statement}
"""
    
    for attempt in range(max_attempts):
        try:
            current_key = api_keys[current_api_key_index]
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(cfg.gemini.model_name)
            response = model.generate_content(prompt)
            variations = response.text.split('===VARIATION===')
            return [v.strip() for v in variations if v.strip()][:num_variations]
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate limit' in error_msg or 'quota' in error_msg or '429' in error_msg:
                print(f"Rate limit hit on API key {current_api_key_index + 1}/{len(api_keys)}. Switching to next key...")
                current_api_key_index = (current_api_key_index + 1) % len(api_keys)
                if attempt == max_attempts - 1:
                    print(f"All API keys exhausted. Waiting 10 seconds before retry...")
                    time.sleep(10)
                else:
                    time.sleep(1)
            else:
                print(f"Error generating variations: {e}")
                return [problem_statement]
    
    print("All API keys exhausted for semantic perturbations")
    return [problem_statement]


def generate_solution_with_context(problem_statement: str, cfg: DictConfig, context: str = "") -> str:
    """Generate solution with optional context about previous failures."""
    global current_api_key_index
    
    api_keys = get_api_keys(cfg)
    max_attempts = len(api_keys)
    
    if context:
        full_prompt = f"{context}\n\n{cfg.gemini.prompt}{problem_statement}"
    else:
        full_prompt = cfg.gemini.prompt + problem_statement
    
    for attempt in range(max_attempts):
        try:
            current_key = api_keys[current_api_key_index]
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(cfg.gemini.model_name)
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate limit' in error_msg or 'quota' in error_msg or '429' in error_msg:
                print(f"Rate limit hit on API key {current_api_key_index + 1}/{len(api_keys)}. Switching to next key...")
                current_api_key_index = (current_api_key_index + 1) % len(api_keys)
                if attempt == max_attempts - 1:
                    print(f"All API keys exhausted. Waiting 10 seconds before retry...")
                    time.sleep(10)
                else:
                    time.sleep(1)
            else:
                print(f"Error generating solution: {e}")
                return ""
    
    return "Error: All API keys exhausted due to rate limits."


@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    # Load user submissions
    user_handle = cfg.user_handle
    submissions_file = f"user_submissions_{user_handle}.json"
    
    print(f"Loading submissions from {submissions_file}...")
    with open(submissions_file, 'r') as f:
        submissions = json.load(f)
    
    # Filter non-OK submissions, excluding specified problems
    EXCLUDE_PROBLEMS = {"2078D", "1805D", "222C", "2135B", "2032D", "1734D", "48C", "2123F"}
    failed_problems = [
        s for s in submissions 
        if s['verdict'] != 'OK' and f"{s['contestId']}{s['index']}" not in EXCLUDE_PROBLEMS
    ]
    failed_problems.sort(key=lambda x: (x.get('rating', 0), x.get('contestId', 0)), reverse=True)
    
    # Filter problems based on modulus for parallel processing
    modulus = cfg.gemini.modulus
    processes = cfg.gemini.processes
    failed_problems = [p for i, p in enumerate(failed_problems) if i % processes == modulus]
    
    print(f"Process {modulus}/{processes}: Processing {len(failed_problems)} of {len(failed_problems)} non-accepted problems")
    
    # Load problem statements
    with open('problem_statements.yaml', 'r', encoding='utf-8') as f:
        problem_statements = yaml.safe_load(f)
    
    # Create lookup dict
    statement_lookup = {
        (p['contestId'], p['index']): p['problem_statement'] 
        for p in problem_statements
    }
    
    results = []
    
    for idx, problem in enumerate(failed_problems, 1):
        contest_id = problem['contestId']
        index = problem['index']
        rating = problem.get('rating', 0)
        verdict = problem['verdict']
        
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(failed_problems)}] Processing {contest_id}{index} (Rating: {rating}, Verdict: {verdict})")
        print(f"{'='*60}")
        
        # Get problem statement
        statement = statement_lookup.get((contest_id, index))
        if not statement:
            print(f"⚠ Problem statement not found for {contest_id}{index}, fetching...")
            try:
                html = get_problem_statement(contest_id, index, cfg.codeforces.cookies)
                statement = parse_problem_statement(html)
                time.sleep(0.5)
            except Exception as e:
                print(f"✗ Error fetching: {e}")
                continue
        
        if not statement or statement == "Problem statement not found.":
            print(f"✗ Could not get problem statement for {contest_id}{index}")
            continue
        
        problem_result = {
            'contestId': contest_id,
            'index': index,
            'rating': rating,
            'verdict': verdict,
            'solutions': {}
        }
        
        # 1. Pass@3 - Generate 3 solutions with failure context
        print(f"\n1. Generating pass@3 solutions...")
        pass_at_3 = []
        previous_code = ""
        for i in range(3):
            context = ""
            if i > 0 and previous_code:
                context = f"Your previous solution failed. Here is the code you generated:\n\n```cpp\n{previous_code}\n```\n\nPlease analyze it and provide a different, corrected solution."
            elif i > 0:
                context = f"Previous attempt {i} failed. Try a different approach."

            print(f"   Generating solution {i+1}/3...")
            solution = generate_solution_with_context(statement, cfg, context)
            code = extract_code(solution)
            previous_code = code  # Save the generated code for the next iteration
            
            pass_at_3.append({
                'attempt': i + 1,
                'full_response': solution,
                'code': code
            })
            time.sleep(0.5)
        problem_result['solutions']['pass_at_3'] = pass_at_3
        
        # 2. Without sample cases
        print(f"\n2. Generating solution without sample cases...")
        statement_no_samples = remove_sample_cases(statement)
        solution = generate_solution_with_context(statement_no_samples, cfg)
        problem_result['solutions']['without_samples'] = {
            'modified_statement': statement_no_samples,
            'full_response': solution,
            'code': extract_code(solution)
        }
        time.sleep(0.5)
        
        # 3. Fudged sample cases
        print(f"\n3. Generating solution with fudged sample cases...")
        statement_fudged = fudge_sample_cases(statement)
        solution = generate_solution_with_context(statement_fudged, cfg)
        problem_result['solutions']['fudged_samples'] = {
            'modified_statement': statement_fudged,
            'full_response': solution,
            'code': extract_code(solution)
        }
        time.sleep(0.5)
        
        # 4. Semantic perturbations
        print(f"\n4. Generating solutions with semantic perturbations...")
        variations = generate_semantic_perturbations(statement, cfg, num_variations=3)
        semantic_solutions = []
        for i, variation in enumerate(variations, 1):
            print(f"   Generating solution for variation {i}/3...")
            solution = generate_solution_with_context(variation, cfg)
            semantic_solutions.append({
                'variation': i,
                'perturbed_statement': variation,
                'full_response': solution,
                'code': extract_code(solution)
            })
            time.sleep(0.5)
        problem_result['solutions']['semantic_perturbations'] = semantic_solutions
        
        results.append(problem_result)
        
        # --- Safe concurrent file writing ---
        output_file = f"solution_variations_{user_handle}.json"
        lock_file = f"{output_file}.lock"
        
        acquire_lock(lock_file)
        try:
            # Read existing data
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                    except json.JSONDecodeError:
                        existing_data = []
            else:
                existing_data = []
            
            # Append new result
            existing_data.append(problem_result)
            
            # Write back to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
        finally:
            release_lock(lock_file)
        
        print(f"\n✓ Completed {contest_id}{index}, saved to {output_file}")
    
    print(f"\n{'='*60}")
    print(f"Generated solution variations for {len(results)} problems")
    print(f"Results saved to solution_variations_{user_handle}.json")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
