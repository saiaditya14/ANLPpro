"""
Problem loader: reads problems from merged.csv and fetches/caches problem statements.
"""

import csv
import os
import re
import time
from typing import List, Dict, Optional

import cloudscraper
from bs4 import BeautifulSoup
from omegaconf import DictConfig


def load_problems_from_csv(csv_path: str) -> List[Dict]:
    """
    Load problems from merged.csv.

    Returns a list of dicts with keys:
        contestId, contestName, problemIndex, problemName,
        waRate, totalSubs, problemUrl, source (codeforces/atcoder)
    """
    problems = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("problemUrl", "")
            # Determine source
            if "codeforces.com" in url:
                source = "codeforces"
            elif "atcoder.jp" in url:
                source = "atcoder"
            else:
                source = "unknown"

            # Parse contest ID and index from URL for CF problems
            contest_id = row.get("contestId", "NA")
            problem_index = row.get("problemIndex", "NA")

            # If contestId is NA, try to parse from URL
            if contest_id == "NA" and source == "codeforces":
                match = re.search(r"/contest/(\d+)/problem/(\w+)", url)
                if not match:
                    match = re.search(r"/problemset/problem/(\d+)/(\w+)", url)
                if match:
                    contest_id = match.group(1)
                    problem_index = match.group(2)

            problems.append({
                "contestId": contest_id,
                "problemIndex": problem_index,
                "contestName": row.get("contestName", "NA"),
                "problemName": row.get("problemName", "NA"),
                "waRate": row.get("waRate", "NA"),
                "totalSubs": row.get("totalSubs", "NA"),
                "problemUrl": url,
                "source": source,
            })

    return problems


def fetch_problem_statement(
    contest_id: str,
    problem_index: str,
    cookie: str = "",
) -> Optional[str]:
    """
    Fetch and parse a Codeforces problem statement.
    Returns the text of the problem statement, or None on failure.
    """
    url = f"https://codeforces.com/contest/{contest_id}/problem/{problem_index}"
    scraper = cloudscraper.create_scraper()

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "referer": f"https://codeforces.com/contest/{contest_id}",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Cookie": cookie,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        response = scraper.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        div = soup.find("div", class_="problem-statement")
        if div:
            return div.get_text(separator="\n", strip=True)
        return None
    except Exception as e:
        print(f"  ✗ Error fetching {contest_id}{problem_index}: {e}")
        return None


def load_and_fetch_problems(
    cfg: DictConfig,
    statement_cache: Optional[Dict] = None,
) -> List[Dict]:
    """
    Load problems from CSV and fetch their statements.

    Args:
        cfg: Hydra config.
        statement_cache: Optional dict mapping (contestId, index) -> statement text.

    Returns:
        List of problem dicts with an additional 'statement' key.
    """
    csv_path = cfg.problems.csv_path
    # Resolve relative path from the original working dir (before Hydra changes cwd)
    original_cwd = os.environ.get("HYDRA_ORIG_CWD", os.getcwd())
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(original_cwd, csv_path)

    print(f"Loading problems from {csv_path}...")
    raw_problems = load_problems_from_csv(csv_path)
    print(f"  Found {len(raw_problems)} problems in CSV")

    # Only process CF problems for now (AtCoder doesn't have the same submission flow)
    cf_problems = [p for p in raw_problems if p["source"] == "codeforces" and p["contestId"] != "NA"]
    print(f"  {len(cf_problems)} Codeforces problems to process")

    if statement_cache is None:
        statement_cache = {}

    cookie = cfg.codeforces.cookies
    enriched = []

    for idx, p in enumerate(cf_problems, 1):
        cid = p["contestId"]
        pidx = p["problemIndex"]
        key = (cid, pidx)

        if key in statement_cache:
            statement = statement_cache[key]
        else:
            print(f"  [{idx}/{len(cf_problems)}] Fetching statement for {cid}{pidx}...")
            statement = fetch_problem_statement(cid, pidx, cookie)
            statement_cache[key] = statement
            time.sleep(0.5)  # Rate-limit

        if statement:
            p["statement"] = statement
            enriched.append(p)
        else:
            print(f"  ✗ Skipping {cid}{pidx} — could not fetch statement")

    print(f"  Successfully loaded {len(enriched)} problems with statements")
    return enriched
