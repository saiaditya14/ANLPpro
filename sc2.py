#!/usr/bin/env python3
"""
cf_dataset_scraper_playwright_fullpatched_v2.py

Robust Playwright-based CF dataset scraper (single reusable browser page).
- Counts EVERY WRONG_ANSWER submission (all occurrences).
- Flags problems with WA-rate >= threshold.
- Scrapes problem statements using Playwright (bypasses Cloudflare JS).
- Robust fetcher tries multiple selectors (including .problemindexholder .ttypography), retries,
  saves debug HTML on failure.
- Options: --show-browser, --debug-slow.

Install:
  pip install requests beautifulsoup4 playwright
  playwright install firefox
"""
from __future__ import annotations
import argparse
import csv
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PWTimeoutError

CF_API_BASE = "https://codeforces.com/api"

# -------------------- utils --------------------

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

# -------------------- CF API helpers --------------------

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
    all_subs: List[Dict[str,Any]] = []
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
    probs_by_index = {p["index"]: p for p in problems}
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

    results: List[Tuple[Dict[str,Any], int, int, float]] = []
    for pidx, p in probs_by_index.items():
        c = counts[pidx]
        total = c["total"]
        wa = c["wa"]
        wa_rate = (wa / total) if total > 0 else 0.0
        results.append((p, wa, total, wa_rate))
    return results

# -------------------- Robust Playwright fetcher (with problemindexholder fallback) --------------------

def _ensure_debug_dir(outdir: str) -> str:
    debug_dir = os.path.join(outdir, "debug_html")
    os.makedirs(debug_dir, exist_ok=True)
    return debug_dir

def fetch_statement_html_with_fallback(page: Page, contest_id: int, pidx: str,
                                       outdir: str = ".",
                                       navigate_timeout: int = 120000,
                                       wait_selector_timeout: int = 90000,
                                       max_attempts: int = 2,
                                       debug_slow: float = 0.0) -> Optional[str]:
    """
    Robust Playwright fetcher:
      - tries two URL patterns (/contest/... and /problemset/problem/...)
      - waits for multiple selectors (fallbacks), including .problemindexholder .ttypography
      - retries and backs off
      - saves final rendered HTML to outdir/debug_html on persistent failure
    """
    urls = [
        f"https://codeforces.com/contest/{contest_id}/problem/{pidx}",
        f"https://codeforces.com/problemset/problem/{contest_id}/{pidx}",
    ]
    selectors = [
        ".problem-statement",                       # typical
        ".problem-text",                            # alternate
        ".problem",                                 # broad fallback
        "#problem-statement",                       # id fallback
        ".problemindexholder .ttypography",         # Kotlin Heroes / EDU style
    ]

    last_html = None
    for url in urls:
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"    [browser] nav attempt {attempt}/{max_attempts} -> {url}")
                page.goto(url, timeout=navigate_timeout)
                page.wait_for_load_state("domcontentloaded", timeout=15000)

                found = None
                start = time.time()
                for sel in selectors:
                    try:
                        remaining = max(2000, wait_selector_timeout - int((time.time() - start) * 1000))
                        page.wait_for_selector(sel, timeout=remaining)
                        handle = page.query_selector(sel)
                        if handle:
                            try:
                                if handle.is_visible():
                                    found = sel
                                    break
                                else:
                                    found = sel
                                    break
                            except Exception:
                                found = sel
                                break
                    except PWTimeoutError:
                        continue

                if found:
                    if debug_slow and debug_slow > 0.0:
                        print(f"    [browser] found selector {found}; pausing {debug_slow:.1f}s for debug view...")
                        time.sleep(debug_slow)
                    html = page.content()
                    return html

                last_html = page.content()
                print(f"    [browser] no matching selector found on attempt {attempt} for {url}")
                time.sleep(1.0 + random.random() * 1.5)
            except PWTimeoutError as te:
                try:
                    last_html = page.content()
                except Exception:
                    last_html = None
                print(f"    [browser] Timeout while loading {url} on attempt {attempt}: {te}")
                time.sleep(1.0 + random.random() * 2.0)
            except Exception as e:
                try:
                    last_html = page.content()
                except Exception:
                    last_html = None
                print(f"    [browser] Exception while loading {url} on attempt {attempt}: {e}")
                time.sleep(1.0 + random.random() * 2.0)

    # persistent failure: save debug html
    debug_dir = _ensure_debug_dir(outdir)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = os.path.join(debug_dir, f"problem_{contest_id}_{pidx}_{ts}.html")
    try:
        with open(fname, "w", encoding="utf-8") as fh:
            if last_html:
                fh.write(last_html)
            else:
                fh.write(f"Failed to fetch {contest_id}/{pidx}. No HTML captured.\n")
        print(f"    [debug] saved rendered HTML to: {fname}")
    except Exception as e:
        print(f"    [debug] failed to save debug HTML: {e}")

    return None

def extract_problem_statement(html: str, keep_samples: bool = True, max_chars: int = 35000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Primary: problem-statement
    ps = soup.find("div", class_="problem-statement")
    # Fallback: problemindexholder .ttypography
    if not ps:
        ps = soup.select_one(".problemindexholder .ttypography")
    # Fallback: any broad wrapper
    if not ps:
        ps = soup.select_one(".problem-text") or soup.select_one(".problem") or soup.select_one("#problem-statement")

    if not ps:
        body = soup.get_text("\n", strip=True)
        return body[:max_chars]

    for el in ps(["script", "style"]):
        el.decompose()
    for selector in ["div.topics", "div.problem-tags", ".problem-tags", ".rating", ".problem-rating"]:
        for el in ps.select(selector):
            el.decompose()
    if not keep_samples:
        for sel in [".sample-test", "div.sample-test", ".input", ".output"]:
            for el in ps.select(sel):
                el.decompose()
    text = ps.get_text("\n", strip=True)
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = "\n".join([ln for ln in lines if ln.strip() != ""])
    return cleaned[:max_chars]

# -------------------- outputs --------------------

def write_outputs(page: Page, outdir: str, contest: Dict[str,Any], flagged: List[Tuple[Dict[str,Any], int,int,float]],
                  keep_samples: bool, debug_slow: float):
    csv_path = os.path.join(outdir, "flagged_problems.csv")
    prompts_dir = os.path.join(outdir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    header_needed = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow(["contestId", "contestName", "problemIndex", "problemName", "waRate", "totalSubs", "problemUrl"])
        for pmeta, wa, total, wa_rate in flagged:
            cid = contest["id"]
            cname = contest.get("name", "").replace('"','')
            pidx = pmeta.get("index")
            pname = pmeta.get("name", "").replace('"','')
            purl = f"https://codeforces.com/contest/{cid}/problem/{pidx}"
            writer.writerow([cid, cname, pidx, pname, f"{wa_rate:.4f}", total, purl])

            html = fetch_statement_html_with_fallback(page, cid, pidx, outdir=outdir, debug_slow=debug_slow)
            if html is None:
                statement = "Problem statement could not be fetched. See debug_html/ for saved HTML."
            else:
                statement = extract_problem_statement(html, keep_samples=keep_samples)

            time_limit = pmeta.get("timeLimit")
            memory_limit = pmeta.get("memoryLimit")
            points = pmeta.get("points")

            prompt_path = os.path.join(prompts_dir, f"prompt_{cid}_{pidx}.txt")
            lines = [
                f"Problem: {pname}",
                f"Contest: {cname}",
                f"URL: {purl}",
                "",
                "--- problem statement (no tags, no rating) ---",
                statement,
                "",
                f"Time limit: {time_limit} ms" if time_limit is not None else "Time limit: (unknown)",
                f"Memory limit: {memory_limit} KB" if memory_limit is not None else "Memory limit: (unknown)",
            ]
            if points is not None:
                lines.append(f"Points: {points}")
            lines.extend(["", "Instruction: Solve."])
            with open(prompt_path, "w", encoding="utf-8") as pf:
                pf.write("\n".join(lines))
    print(f"Wrote CSV and prompts to {outdir}")

# -------------------- main --------------------

def main():
    parser = argparse.ArgumentParser(description="Flag CF problems and fetch statements with Playwright (robust).")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--wa-threshold", required=True, type=float, help="WA threshold as decimal (e.g., 0.2)")
    parser.add_argument("--outdir", default="cf_dataset_output", help="Output dir")
    parser.add_argument("--page-size", type=int, default=5000)
    parser.add_argument("--min-delay", type=float, default=0.3)
    parser.add_argument("--max-delay", type=float, default=1.2)
    parser.add_argument("--include-practice", action="store_true", help="Include PRACTICE submissions")
    parser.add_argument("--include-virtual", action="store_true", help="Include VIRTUAL submissions")
    parser.add_argument("--keep-samples", action="store_true", help="Keep sample tests in scraped statement")
    parser.add_argument("--show-browser", action="store_true", help="Launch browser headful so you can watch navigation")
    parser.add_argument("--debug-slow", type=float, default=0.0, help="If >0, sleep this many seconds after each page navigation (only useful with --show-browser)")
    args = parser.parse_args()

    start_unix = to_unix(args.start)
    end_unix = to_unix(args.end) + 86399

    exclude_types: List[str] = []
    if not args.include_practice:
        exclude_types.append("PRACTICE")
    if not args.include_virtual:
        exclude_types.append("VIRTUAL")

    session = requests.Session()
    session.headers.update({"User-Agent": "CF-Dataset-Scraper/Playwright-Fallback-v2/1.0"})

    contests = list_contests(session, start_unix, end_unix)
    os.makedirs(args.outdir, exist_ok=True)
    total_flagged = 0

    with sync_playwright() as pw:
        browser: Browser = pw.firefox.launch(headless=not args.show_browser)
        page: Page = browser.new_page()
        page.set_viewport_size({"width": 1200, "height": 900})

        for c in contests:
            cid = c["id"]
            cname = c.get("name","<no-name>")
            st = datetime.fromtimestamp(c.get("startTimeSeconds",0), tz=timezone.utc)
            print(f"\nProcessing contest {cid} - {cname} ({st.isoformat()})")
            try:
                problems = fetch_problems(session, cid)
                time.sleep(random.uniform(args.min_delay, args.max_delay))

                subs = fetch_submissions(session, cid, page_size=args.page_size,
                                         min_delay=args.min_delay, max_delay=args.max_delay)
                rates = compute_rates_allwa(problems, subs, exclude_participant_types=exclude_types)
                flagged = [(pmeta, wa, total, wa_rate)
                           for (pmeta, wa, total, wa_rate) in rates if total > 0 and wa_rate >= args.wa_threshold]
                if flagged:
                    print(f"  Flagged {len(flagged)} problems in contest {cid}")
                    write_outputs(page, args.outdir, c, flagged, keep_samples=args.keep_samples, debug_slow=args.debug_slow)
                    total_flagged += len(flagged)
                else:
                    print("  No flagged problems in this contest.")
                time.sleep(random.uniform(args.min_delay*1.5, args.max_delay*2.5))
            except Exception as e:
                print(f"  ERROR processing contest {cid}: {e}")
                time.sleep(random.uniform(args.min_delay, args.max_delay))

        print("Closing browser...")
        browser.close()

    print("\nDone. Total flagged problems:", total_flagged)
    print("Output dir:", os.path.abspath(args.outdir))
    print("CSV: flagged_problems.csv, prompts/, debug_html/")

if __name__ == "__main__":
    main()
