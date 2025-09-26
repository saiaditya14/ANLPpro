#!/usr/bin/env python3
"""
cf_flagger_allwa.py

Counts EVERY WRONG_ANSWER submission (including repeated WAs by same users) for Codeforces problems
in a date window and flags problems whose WA-rate >= threshold.

Key differences from previous script:
 - WA definition: count ALL WRONG_ANSWER verdicts (every submission) as WA.
 - COMPILATION_ERROR submissions are ignored (not counted as relevant).
 - Other features: random delays, retries/backoff, excludes PRACTICE/VIRTUAL by default, writes CSV + prompts.

Dependencies:
  pip install requests
"""
import argparse
import csv
import json
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import requests

CF_API_BASE = "https://codeforces.com/api"

def to_unix(datestr: str) -> int:
    dt = datetime.fromisoformat(datestr)
    dt_utc = dt.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(dt_utc.timestamp())

def safe_request(session: requests.Session, url: str, params: dict = None,
                 max_retries: int = 5, backoff_factor: float = 1.6) -> dict:
    params = params or {}
    attempt = 0
    while True:
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            elif r.status_code in (429, 502, 503, 504):
                attempt += 1
                if attempt > max_retries:
                    raise RuntimeError(f"HTTP {r.status_code} from {url} after {attempt} attempts")
                sleep = (backoff_factor ** attempt) + random.uniform(0, 1.0)
                print(f"Transient HTTP {r.status_code}; retry {attempt}/{max_retries} after {sleep:.1f}s")
                time.sleep(sleep)
                continue
            else:
                raise RuntimeError(f"HTTP {r.status_code} from {url}: {r.text[:400]}")
        except requests.RequestException as e:
            attempt += 1
            if attempt > max_retries:
                raise RuntimeError(f"Request to {url} failed after {attempt} attempts: {e}")
            sleep = (backoff_factor ** attempt) + random.uniform(0, 1.0)
            print(f"Request exception; retry {attempt}/{max_retries} after {sleep:.1f}s: {e}")
            time.sleep(sleep)

def list_contests(session: requests.Session, start_unix: int, end_unix: int) -> List[Dict[str,Any]]:
    print("Fetching contest list...")
    resp = safe_request(session, f"{CF_API_BASE}/contest.list")
    if resp.get("status") != "OK":
        raise RuntimeError("contest.list failed")
    contests = resp["result"]
    filtered = [c for c in contests if c.get("startTimeSeconds") and start_unix <= c["startTimeSeconds"] <= end_unix]
    filtered.sort(key=lambda x: x["startTimeSeconds"])
    print(f"Found {len(filtered)} contests.")
    return filtered

def fetch_problems(session: requests.Session, contest_id: int) -> List[Dict[str,Any]]:
    resp = safe_request(session, f"{CF_API_BASE}/contest.standings", {"contestId": contest_id, "from": 1, "count": 1})
    if resp.get("status") != "OK":
        raise RuntimeError(f"contest.standings failed for {contest_id}")
    return resp["result"].get("problems", [])

def fetch_submissions(session: requests.Session, contest_id: int, page_size: int,
                      min_delay: float, max_delay: float) -> List[Dict[str,Any]]:
    all_subs = []
    offset = 1
    while True:
        params = {"contestId": contest_id, "from": offset, "count": page_size}
        print(f"  fetching submissions {offset}..{offset+page_size-1} for contest {contest_id}")
        resp = safe_request(session, f"{CF_API_BASE}/contest.status", params)
        if resp.get("status") != "OK":
            raise RuntimeError(f"contest.status failed for {contest_id} offset {offset}")
        subs = resp.get("result", [])
        if not subs:
            break
        all_subs.extend(subs)
        if len(subs) < page_size:
            break
        offset += page_size
        time.sleep(random.uniform(min_delay, max_delay))
    print(f"  total submissions fetched: {len(all_subs)}")
    return all_subs

def compute_rates_allwa(problems: List[Dict[str,Any]], submissions: List[Dict[str,Any]],
                        exclude_participant_types: List[str]) -> List[Tuple[Dict[str,Any], int, int, float]]:
    """
    Count every relevant submission:
      - Relevant = verdict not null, verdict != 'TESTING', verdict != 'COMPILATION_ERROR'
      - WA_count = number of submissions whose verdict == 'WRONG_ANSWER'
      - total_count = number of relevant submissions (all verdicts except testing/ce/null)
    Excludes submissions where author.participantType is in exclude_participant_types.
    """
    probs_by_index = {p["index"]: p for p in problems}
    # initialize counts
    counts = {pidx: {"wa": 0, "total": 0} for pidx in probs_by_index.keys()}
    for s in submissions:
        prob = s.get("problem")
        if not prob:
            continue
        pidx = prob.get("index")
        if pidx not in counts:
            continue
        author = s.get("author")
        if not author:
            continue
        part_type = author.get("participantType", "")
        if part_type in exclude_participant_types:
            continue
        verdict = s.get("verdict")
        if verdict is None or verdict == "TESTING" or verdict == "COMPILATION_ERROR":
            continue
        counts[pidx]["total"] += 1
        if verdict == "WRONG_ANSWER":
            counts[pidx]["wa"] += 1

    results = []
    for pidx, p in probs_by_index.items():
        c = counts[pidx]
        total = c["total"]
        wa = c["wa"]
        wa_rate = (wa / total) if total > 0 else 0.0
        results.append((p, wa, total, wa_rate))
    return results

def write_outputs(outdir: str, contest: Dict[str,Any], flagged: List[Tuple[Dict[str,Any], int,int,float]]):
    csv_path = os.path.join(outdir, "flagged_problems.csv")
    prompts_dir = os.path.join(outdir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    header_needed = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow(["contestId", "contestName", "problemIndex", "problemName", "waRate", "totalSubs", "problemUrl"])
        for p, wa, total, wa_rate in flagged:
            cid = contest["id"]
            cname = contest.get("name", "").replace('"','')
            pidx = p.get("index")
            pname = p.get("name", "").replace('"','')
            purl = f"https://codeforces.com/contest/{cid}/problem/{pidx}"
            writer.writerow([cid, cname, pidx, pname, f"{wa_rate:.4f}", total, purl])
            prompt_path = os.path.join(prompts_dir, f"prompt_{cid}_{pidx}.txt")
            lines = [
                f"Problem: {pname}",
                f"Contest: {cname} (id={cid})",
                f"URL: {purl}",
                "",
                "--- problem metadata (not full statement) ---",
                json.dumps(p, ensure_ascii=False, indent=2)[:1200],
                "",
                "Instruction: Solve."
            ]
            with open(prompt_path, "w", encoding="utf-8") as pf:
                pf.write("\n".join(lines))
    print(f"Wrote CSV and prompts to {outdir}")

def main():
    parser = argparse.ArgumentParser(description="Flag CF problems by counting ALL WRONG_ANSWER submissions.")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--wa-threshold", required=True, type=float, help="WA threshold as decimal (e.g., 0.2)")
    parser.add_argument("--outdir", default="cf_flags_output_allwa", help="Output dir")
    parser.add_argument("--page-size", type=int, default=5000)
    parser.add_argument("--min-delay", type=float, default=0.3)
    parser.add_argument("--max-delay", type=float, default=1.2)
    parser.add_argument("--include-practice", action="store_true", help="Include PRACTICE submissions")
    parser.add_argument("--include-virtual", action="store_true", help="Include VIRTUAL submissions")
    args = parser.parse_args()

    start_unix = to_unix(args.start)
    end_unix = to_unix(args.end) + 86399

    exclude_types = []
    if not args.include_practice:
        exclude_types.append("PRACTICE")
    if not args.include_virtual:
        exclude_types.append("VIRTUAL")

    session = requests.Session()
    session.headers.update({"User-Agent": "CF-Flagger-AllWA/1.0 (research)"})

    contests = list_contests(session, start_unix, end_unix)
    os.makedirs(args.outdir, exist_ok=True)
    total_flagged = 0

    for c in contests:
        cid = c["id"]
        cname = c.get("name","<no-name>")
        st = datetime.fromtimestamp(c.get("startTimeSeconds",0), tz=timezone.utc)
        print(f"\nProcessing contest {cid} - {cname} ({st.isoformat()})")
        try:
            problems = fetch_problems(session, cid)
            time.sleep(random.uniform(args.min_delay, args.max_delay))
            subs = fetch_submissions(session, cid, page_size=args.page_size, min_delay=args.min_delay, max_delay=args.max_delay)
            rates = compute_rates_allwa(problems, subs, exclude_participant_types=exclude_types)
            flagged = [(p, wa, total, wa_rate) for (p, wa, total, wa_rate) in rates if total > 0 and wa_rate >= args.wa_threshold]
            if flagged:
                print(f"  Flagged {len(flagged)} problems in contest {cid}")
                write_outputs(args.outdir, c, flagged)
                total_flagged += len(flagged)
            else:
                print("  No flagged problems in this contest.")
            time.sleep(random.uniform(args.min_delay*1.5, args.max_delay*2.5))
        except Exception as e:
            print(f"  ERROR processing contest {cid}: {e}")
            time.sleep(random.uniform(args.min_delay, args.max_delay))

    print("\nDone. Total flagged problems:", total_flagged)
    print("Output dir:", os.path.abspath(args.outdir))
    print("CSV: flagged_problems.csv, prompts/")

if __name__ == "__main__":
    main()
