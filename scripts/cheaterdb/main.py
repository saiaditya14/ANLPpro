import json
import time
from datetime import datetime, timedelta
import hydra
from omegaconf import DictConfig

from typing import Dict, List, Set, Optional
from collections import defaultdict, Counter

from cf_api import CodeforcesAPI

def load_user_list(file_path: str) -> List[str]:
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data.get('cheaters', [])
    except FileNotFoundError:
        print(f"File {file_path} not found")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return []

def analyze_submissions(submissions: List[Dict], api: CodeforcesAPI, cfg: DictConfig) -> Dict:
    cutoff_date = datetime.now() - timedelta(days=cfg.analysis.days_to_analyze)
    
    recent_submissions = []
    for submission in submissions:
        submission_time = datetime.fromtimestamp(submission.get('creationTimeSeconds', 0))
        if submission_time >= cutoff_date:
            recent_submissions.append(submission)
    
    if cfg.processing.enable_debug:
        print(f"    Filtered to {len(recent_submissions)} submissions from last {cfg.analysis.days_to_analyze} days (out of {len(submissions)} total)")
    
    # group submissions by problem
    problem_submissions = defaultdict(list)
    
    for submission in recent_submissions:
        problem = submission.get('problem', {})
        problem_key = f"{problem.get('contestId', 'unknown')}_{problem.get('index', 'unknown')}"
        problem_submissions[problem_key].append(submission)
    
    suspicious_problems = {}
    
    for problem_key, prob_submissions in problem_submissions.items():
        verdict_counts = Counter()
        
        for sub in prob_submissions:
            verdict = sub.get('verdict', 'UNKNOWN')
            verdict_counts[verdict] += 1
        
        problematic_verdicts = ['WRONG_ANSWER', 'RUNTIME_ERROR', 'TIME_LIMIT_EXCEEDED']
        total_problematic = sum(verdict_counts[v] for v in problematic_verdicts)
        
        if total_problematic > cfg.analysis.max_problematic_threshold:
            problem_info = prob_submissions[0].get('problem', {})
            contest_id = problem_info.get('contestId')
            problem_index = problem_info.get('index')
            
            # get problem rating
            problem_rating = None
            if contest_id and problem_index:
                contest_info = api.get_contest_info(contest_id)
                if contest_info and problem_index in contest_info['problems']:
                    problem_rating = contest_info['problems'][problem_index].get('rating')
                    
                    if problem_rating is None or problem_rating <= cfg.analysis.max_rating_threshold:
                        suspicious_problems[problem_key] = {
                            'problem_name': problem_info.get('name', 'Unknown'),
                            'contest_id': contest_id,
                            'problem_index': problem_index,
                            'problem_rating': problem_rating,
                            'total_submissions': len(prob_submissions),
                            'wa_count': verdict_counts['WRONG_ANSWER'],
                            'rte_count': verdict_counts['RUNTIME_ERROR'],
                            'tle_count': verdict_counts['TIME_LIMIT_EXCEEDED'],
                            'total_problematic': total_problematic,
                            'accepted_count': verdict_counts['OK'],
                            'verdict_distribution': dict(verdict_counts),
                            'submission_period': f'last_{cfg.analysis.days_to_analyze}_days'
                        }
                        if cfg.processing.enable_debug:
                            print(f"    Added suspicious problem: {problem_info.get('name')} (rating: {problem_rating})")
                    else:
                        if cfg.processing.enable_debug:
                            print(f"    Skipped problem {problem_info.get('name')} - rating {problem_rating} > {cfg.analysis.max_rating_threshold}")
                else:
                    if cfg.processing.enable_debug:
                        print(f"    Could not get rating for problem {problem_key}")
                    time.sleep(cfg.api.delay_between_requests * 0.2)
    
    return suspicious_problems

@hydra.main(version_base=None, config_path=".", config_name="config")
def main(cfg: DictConfig):
    # Load user list with optional limit for testing
    all_users = load_user_list(cfg.files.user_list)
    user_list = all_users[cfg.processing.users_l:cfg.processing.users_r] if cfg.processing.users_r else all_users
    
    print(f"Loaded {len(user_list)} users from {cfg.files.user_list}")
    if cfg.processing.users_r and cfg.processing.users_l:
        print(f"Testing with users from index {cfg.processing.users_l} to {cfg.processing.users_r}")
    
    if not user_list:
        print("No users found in user list file")
        return
    
    api = CodeforcesAPI(cfg)
    
    if not api.api_key or not api.api_secret:
        print("Warning: API KEY or SECRET not found in environment variables")
        print("Some requests might be rate-limited")
    
    all_suspicious_users = {}
    
    for i, username in enumerate(user_list):
        print(f"Processing user {i+1}/{len(user_list)}: {username}")
        
        submissions = api.get_user_submissions(username)
        
        if submissions:
            suspicious_problems = analyze_submissions(submissions, api, cfg)
            
            if suspicious_problems:
                all_suspicious_users[username] = {
                    'total_submissions': len(submissions),
                    'suspicious_problems_count': len(suspicious_problems),
                    'suspicious_problems': suspicious_problems
                }
                print(f"  Found {len(suspicious_problems)} suspicious problems for {username}")
            else:
                print(f"  No suspicious problems found for {username}")
        else:
            print(f"  No submissions found for {username}")
        
        # Rate limiting
        if (i + 1) % cfg.api.batch_size == 0:
            print(f"Processed {i+1} users, sleeping for {cfg.api.batch_delay} seconds...")
            time.sleep(cfg.api.batch_delay)
        else:
            time.sleep(cfg.api.delay_between_requests)
    
    # Save all results
    with open(cfg.files.output_all, 'w') as f:
        json.dump(all_suspicious_users, f, indent=2)

    # Create a simplified list of unique problems for the filtered output
    unique_problems = {}
    for username, data in all_suspicious_users.items():
        for problem_key, problem_data in data['suspicious_problems'].items():
            if problem_key not in unique_problems:
                unique_problems[problem_key] = {
                    'contestId': problem_data['contest_id'],
                    'index': problem_data['problem_index'],
                    'name': problem_data['problem_name'],
                    'rating': problem_data['problem_rating']
                }

    # Save the simplified list of problems
    with open(cfg.files.output_filtered, 'w') as f:
        json.dump(list(unique_problems.values()), f, indent=2)

    # Print analysis summary
    print(f"\nANALYSIS COMPLETE")
    print(f"Total users analyzed: {len(user_list)}")
    print(f"Users with suspicious patterns (all): {len(all_suspicious_users)}")
    print(f"Total unique suspicious problems found: {len(unique_problems)}")
    print(f"All results saved to: {cfg.files.output_all}")
    print(f"Filtered problem list saved to: {cfg.files.output_filtered}")

if __name__ == "__main__":
    main()
