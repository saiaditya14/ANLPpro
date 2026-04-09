"""
Codeforces solution submission with configurable timeouts.
Extracted and enhanced from the original cheaterdb/problems.py.
"""

import re
import time
from typing import Optional, Tuple

import cloudscraper
from bs4 import BeautifulSoup
from omegaconf import DictConfig


def get_submission_details(
    scraper: cloudscraper.CloudScraper,
    contest_id: str,
    problem_index: str,
    cookie: str = "",
    timeout: int = 30,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Fetch CSRF token, ftaa, and bfaa from the CF submit page.
    """
    submit_page_url = f"https://codeforces.com/contest/{contest_id}/submit"

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "referer": submit_page_url,
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "cookie": cookie,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        response = scraper.get(submit_page_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        html = response.text

        if "Submit solution" not in html and "submit" not in html.lower():
            print(f"    [WARN] Submit page did not load properly")
            return None, None, None

        soup = BeautifulSoup(html, "lxml")
        csrf_input = soup.find("input", {"name": "csrf_token"})
        if not csrf_input:
            print(f"    [WARN] CSRF token not found on submit page")
            return None, None, None

        csrf_token = csrf_input["value"]

        ftaa_match = re.search(r'window\._ftaa\s*=\s*"(.*?)"', html)
        bfaa_match = re.search(r'window\._bfaa\s*=\s*"(.*?)"', html)
        ftaa = ftaa_match.group(1) if ftaa_match else ""
        bfaa = bfaa_match.group(1) if bfaa_match else ""

        return csrf_token, ftaa, bfaa
    except Exception as e:
        print(f"    ✗ Error fetching submission details: {e}")
        return None, None, None


def submit_solution(
    scraper: cloudscraper.CloudScraper,
    contest_id: str,
    problem_index: str,
    code: str,
    csrf_token: str,
    ftaa: str,
    bfaa: str,
    cfg: DictConfig,
) -> bool:
    """
    Submit a solution to Codeforces.

    Returns True if submission appeared successful (redirected to status page).
    """
    submit_url = (
        f"https://codeforces.com/contest/{contest_id}/submit"
        f"?adcd1e={cfg.codeforces.adcd1e}&csrf_token={csrf_token}"
    )

    payload = {
        "csrf_token": csrf_token,
        "ftaa": ftaa,
        "bfaa": bfaa,
        "action": "submitSolutionFormSubmitted",
        "submittedProblemIndex": problem_index,
        "programTypeId": str(cfg.codeforces.program_type_id),
        "source": code,
        "tabSize": "4",
        "sourceFile": "",
        "_tta": str(cfg.codeforces.get("tta", "")),
    }
    
    # Add Cloudflare Turnstile tokens if configured
    turnstile = cfg.codeforces.get("turnstile_token", "")
    if turnstile:
        payload["turnstileToken"] = turnstile
        payload["cf-turnstile-response"] = turnstile

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "referer": f"https://codeforces.com/contest/{contest_id}/submit",
        "origin": "https://codeforces.com",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "cookie": cfg.codeforces.cookies,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    timeout = cfg.codeforces.submit_timeout

    try:
        response = scraper.post(
            submit_url, data=payload, headers=headers,
            allow_redirects=True, timeout=timeout,
        )

        if "/problemset/status" in response.url or response.url.endswith("/my"):
            print(f"    ✓ Successfully submitted {contest_id}{problem_index}")
            return True
        else:
            print(f"    ✗ Submission may have failed for {contest_id}{problem_index}. "
                  f"Redirected to: {response.url}")
            return False
    except Exception as e:
        print(f"    ✗ Error submitting {contest_id}{problem_index}: {e}")
        return False


def submit_code_for_problem(
    contest_id: str,
    problem_index: str,
    code: str,
    cfg: DictConfig,
) -> bool:
    """
    High-level helper: create scraper, get CSRF, and submit.
    Respects cfg.codeforces.delay_between_submits.
    """
    if not cfg.codeforces.submit_solutions:
        return False

    if not code or "No C++ code block found" in code:
        print(f"    ✗ No valid code to submit for {contest_id}{problem_index}")
        return False

    scraper = cloudscraper.create_scraper()
    csrf_token, ftaa, bfaa = get_submission_details(
        scraper, contest_id, problem_index,
        cfg.codeforces.cookies, cfg.codeforces.submit_timeout,
    )

    if not csrf_token:
        print(f"    ✗ Could not get submission details for {contest_id}{problem_index}")
        return False

    result = submit_solution(
        scraper, contest_id, problem_index,
        code, csrf_token, ftaa, bfaa, cfg,
    )

    # Rate-limit between submissions
    time.sleep(cfg.codeforces.delay_between_submits)
    return result
