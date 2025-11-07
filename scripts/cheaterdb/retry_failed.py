#!/usr/bin/env python3
"""
Retry script for unsubmitted problems.
Loads problems from filtered_problems JSON, excludes user submissions,
applies rating filters, and processes with modulus support.
"""

import time
import json
import cloudscraper
import hydra
from omegaconf import DictConfig
from problems import (
    get_problem_statement,
    parse_problem_statement,
    generate_solution,
    extract_code,
    get_submission_details,
    submit_solution
)


def load_problems_and_submissions(cfg: DictConfig):
    """Load problems from filtered JSON and user submissions."""
    # Load all problems
    problems_file = cfg.files.output_filtered
    with open(problems_file, 'r') as f:
        all_problems = json.load(f)
    
    # Load user submissions
    user_handle = cfg.user_handle
    submissions_file = f"user_submissions_{user_handle}.json"
    try:
        with open(submissions_file, 'r') as f:
            user_submissions = json.load(f)
    except FileNotFoundError:
        print(f"Warning: {submissions_file} not found. Run fetch_user_submissions.py first.")
        user_submissions = []
    
    # Create set of submitted problems for quick lookup
    submitted = {(s['contestId'], s['index']) for s in user_submissions}
    
    # Filter problems: not submitted + rating filters
    min_rating = cfg.analysis.min_rating_threshold
    max_rating = cfg.analysis.max_rating_threshold
    
    unsubmitted_problems = []
    for problem in all_problems:
        contest_id = problem['contestId']
        index = problem['index']
        rating = problem.get('rating', 0)
        
        # Skip if already submitted
        if (contest_id, index) in submitted:
            continue
        
        # Apply rating filter (include unrated problems with rating=0)
        if rating != 0 and (rating < min_rating or rating > max_rating):
            continue
        
        unsubmitted_problems.append(problem)
    
    return unsubmitted_problems, len(user_submissions), len(all_problems)


@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    # Load problems and user submissions
    unsubmitted_problems, num_submissions, total_problems = load_problems_and_submissions(cfg)
    
    print(f"Total problems in filtered list: {total_problems}")
    print(f"User submissions found: {num_submissions}")
    print(f"Unsubmitted problems (within rating range): {len(unsubmitted_problems)}")
    print(f"Rating range: {cfg.analysis.min_rating_threshold}-{cfg.analysis.max_rating_threshold}")
    
    # Filter problems based on modulus for parallel processing
    modulus = cfg.gemini.modulus
    processes = cfg.gemini.processes
    problems_to_retry = [p for i, p in enumerate(unsubmitted_problems) if i % processes == modulus]
    
    print(f"\nProcess {modulus}/{processes}: Processing {len(problems_to_retry)} problems")
    
    submissions_count = 0
    total_to_process = len(problems_to_retry)
    
    for problem_info in problems_to_retry:
        contest_id = problem_info['contestId']
        problem_index = problem_info['index']
        rating = problem_info.get('rating', 'unrated')
        print(f"\n{'='*60}")
        print(f"Processing problem: {contest_id}{problem_index} (Rating: {rating})")
        print(f"{'='*60}")
        
        # Try to fetch the problem statement
        try:
            html_content = get_problem_statement(contest_id, problem_index, cfg.codeforces.cookies)
            statement = parse_problem_statement(html_content)
            
            if statement:
                print(f"✓ Successfully fetched problem {contest_id}{problem_index}")
                print(f"Generating solution for {contest_id}{problem_index}...")
                solution_text = generate_solution(statement, cfg)
                extracted_code = extract_code(solution_text)
                
                if "No C++ code block found" not in extracted_code:
                    print(f"✓ Code extracted successfully")
                    print(f"--- Submitting Solution for {contest_id}{problem_index} ---")
                    scraper = cloudscraper.create_scraper() 
                    csrf_token, ftaa, bfaa = get_submission_details(scraper, contest_id, problem_index, cfg.codeforces.cookies)
                    
                    if csrf_token:
                        submit_solution(scraper, contest_id, problem_index, extracted_code, csrf_token, ftaa, bfaa, cfg)
                        submissions_count += 1
                        print(f"✓ Submitted {submissions_count}/{total_to_process} problems so far")
                    else:
                        print("✗ Could not submit solution, submission details not found.")
                else:
                    print(f"✗ Could not extract code for {contest_id}{problem_index}, skipping submission.")
            else:
                print(f"✗ Could not parse problem statement for {contest_id}{problem_index}")
                
        except Exception as e:
            print(f"✗ Error processing problem {contest_id}{problem_index}: {e}")
        
        # Rate limit: 2 requests per second (0.5 second delay between requests)
        time.sleep(0.5)
    
    print(f"\n{'='*60}")
    print(f"Process complete! Submitted {submissions_count}/{total_to_process} problems")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
