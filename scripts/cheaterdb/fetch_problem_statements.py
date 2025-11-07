#!/usr/bin/env python3
"""
Fetch problem statements from filtered problems and save to YAML.
"""

import json
import yaml
import time
import hydra
from omegaconf import DictConfig
from problems import get_problem_statement, parse_problem_statement


def load_problems_and_submissions(cfg: DictConfig):
    """Load problems from filtered JSON and user submissions."""
    problems_file = cfg.files.output_filtered
    with open(problems_file, 'r') as f:
        all_problems = json.load(f)
    
    user_handle = cfg.user_handle
    submissions_file = f"user_submissions_{user_handle}.json"
    try:
        with open(submissions_file, 'r') as f:
            user_submissions = json.load(f)
    except FileNotFoundError:
        print(f"Warning: {submissions_file} not found. Will process all problems.")
        user_submissions = []
    
    submitted = {(s['contestId'], s['index']) for s in user_submissions}
    
    min_rating = cfg.analysis.min_rating_threshold
    max_rating = cfg.analysis.max_rating_threshold
    
    unsubmitted_problems = []
    for problem in all_problems:
        contest_id = problem['contestId']
        index = problem['index']
        rating = problem.get('rating', 0)
        
        if (contest_id, index) in submitted:
            continue
        
        if rating != 0 and (rating < min_rating or rating > max_rating):
            continue
        
        unsubmitted_problems.append(problem)
    
    return unsubmitted_problems


@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    problems = load_problems_and_submissions(cfg)
    
    print(f"Loading {len(problems)} problems...")
    print(f"Rating range: {cfg.analysis.min_rating_threshold}-{cfg.analysis.max_rating_threshold}")
    
    print(f"Fetching {len(problems)} problems")
    
    problem_statements = []
    
    for idx, problem_info in enumerate(problems):
        contest_id = problem_info['contestId']
        problem_index = problem_info['index']
        rating = problem_info.get('rating', 0)
        
        print(f"\n[{idx+1}/{len(problems)}] Fetching {contest_id}{problem_index} (Rating: {rating})")
        
        try:
            html_content = get_problem_statement(contest_id, problem_index, cfg.codeforces.cookies)
            statement = parse_problem_statement(html_content)
            
            if statement:
                problem_data = {
                    'contestId': contest_id,
                    'index': problem_index,
                    'rating': rating,
                    'problem_statement': statement
                }
                problem_statements.append(problem_data)
                print(f"✓ Successfully fetched {contest_id}{problem_index}")
            else:
                print(f"✗ Could not parse problem statement for {contest_id}{problem_index}")
                
        except Exception as e:
            print(f"✗ Error fetching {contest_id}{problem_index}: {e}")
        
        # Rate limit: 2 requests per second (0.5 second delay between requests)
        time.sleep(0.5)
    
    output_file = f"problem_statements.yaml"
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(problem_statements, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    print(f"\n{'='*60}")
    print(f"Saved {len(problem_statements)} problem statements to {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
