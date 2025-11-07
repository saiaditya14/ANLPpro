import json
import yaml
import time
import hydra
from omegaconf import DictConfig
from problems import get_problem_statement, parse_problem_statement


@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    # Load problems from output_filtered file
    problems_file = cfg.files.output_filtered
    print(f"Loading problems from {problems_file}...")
    
    with open(problems_file, 'r') as f:
        problems = json.load(f)
    
    problems = [p for p in problems if p.get('rating', 0) == 1800]

    print(f"Found {len(problems)} problems to fetch")
    
    problem_statements = []
    
    for idx, problem_info in enumerate(problems, 1):
        contest_id = problem_info['contestId']
        problem_index = problem_info['index']
        rating = problem_info.get('rating', 0)
        
        print(f"\n[{idx}/{len(problems)}] Fetching {contest_id}{problem_index} (Rating: {rating})")
        
        try:
            html_content = get_problem_statement(contest_id, problem_index, cfg.codeforces.cookies)
            statement = parse_problem_statement(html_content)
            
            if statement and statement != "Problem statement not found.":
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
        
        # Rate limit: 1 requests per second
        time.sleep(1)
    
    # Save to YAML
    output_file = "problem_statements.yaml"
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(problem_statements, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    print(f"\n{'='*60}")
    print(f"Successfully saved {len(problem_statements)}/{len(problems)} problem statements to {output_file}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
