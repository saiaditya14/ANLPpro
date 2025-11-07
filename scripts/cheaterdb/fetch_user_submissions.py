import json
import hydra
from omegaconf import DictConfig
from cf_api import CodeforcesAPI
import dotenv

dotenv.load_dotenv()
@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    cf_api = CodeforcesAPI(cfg)
    
    handle = cfg.get("user_handle", "")
    if not handle:
        print("Error: user_handle not set in config")
        return
    
    print(f"Fetching submissions for user: {handle}")
    submissions = cf_api.get_user_submissions(handle)
    
    if not submissions:
        print("No submissions found or error occurred")
        return
    
    print(f"Found {len(submissions)} submissions")
    
    result = []
    for sub in submissions:
        problem = sub.get("problem", {})
        contest_id = problem.get("contestId")
        index = problem.get("index")
        rating = problem.get("rating")
        verdict = sub.get("verdict", "UNKNOWN")
        
        result.append({
            "contestId": contest_id,
            "index": index,
            "rating": rating,
            "verdict": verdict
        })
    
    output_file = f"user_submissions_{handle}.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Saved {len(result)} submissions to {output_file}")
    
    verdict_counts = {}
    for item in result:
        verdict = item["verdict"]
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
    
    print("\nVerdict summary:")
    for verdict, count in sorted(verdict_counts.items(), key=lambda x: -x[1]):
        print(f"  {verdict}: {count}")


if __name__ == "__main__":
    main()
