import cloudscraper
from bs4 import BeautifulSoup
import json
import hydra
from omegaconf import DictConfig
import time
import google.generativeai as genai
import re
from dotenv import load_dotenv

load_dotenv()

# Global variable to track current API key index
current_api_key_index = 0

def get_api_keys(cfg: DictConfig):
    """Parse comma-separated API keys from config."""
    keys_str = cfg.gemini.api_keys
    return [key.strip() for key in keys_str.split(',') if key.strip()]

def get_problem_statement(contest_id, problem_index, cookie=""):
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}"
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'firefox',
            'platform': 'darwin',
            'mobile': False
        }
    )
    
    # Headers adapted from the provided curl request
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'referer': 'https://codeforces.com/problemset',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-arch': '"arm"',
        'sec-ch-ua-bitness': '"64"',
        'sec-ch-ua-full-version': '"140.0.7339.215"',
        'sec-ch-ua-full-version-list': '"Chromium";v="140.0.7339.215", "Not=A?Brand";v="24.0.0.0", "Google Chrome";v="140.0.7339.215"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"macOS"',
        'sec-ch-ua-platform-version': '"15.6.1"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        'priority': 'u=0, i',
        'Cookie': cookie,
    }

    try:
        response = scraper.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching problem {contest_id}{problem_index}: {e}")
        return None

def parse_problem_statement(html_content):
    if not html_content:
        return None
    soup = BeautifulSoup(html_content, 'lxml')
    problem_statement_div = soup.find('div', class_='problem-statement')
    if problem_statement_div:
        return problem_statement_div.get_text(separator='\n', strip=True)
    return "Problem statement not found."

def extract_code(gemini_response: str) -> str:
    code_block_match = re.search(r'```cpp\n(.*?)```', gemini_response, re.DOTALL)
    if code_block_match:
        return code_block_match.group(1).strip()
    
    code_block_match = re.search(r'```(.*?)```', gemini_response, re.DOTALL)
    if code_block_match:
        return code_block_match.group(1).strip()
        
    return "No C++ code block found in the response."

def get_submission_details(scraper, contest_id, index, cookie=""):
    submit_page_url = f"https://codeforces.com/problemset/submit"
    
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'referer': 'https://codeforces.com/problemset/submit',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        'connection': 'keep-alive',
        'cookie': cookie,
        'priority': 'u=0, i',
        'te': 'trailers',
    }

    try:
        response = scraper.get(submit_page_url, headers=headers)
        response.raise_for_status()
        html_content = response.text
        
        # Debug: Check if we got the right page
        if "Submit solution" not in html_content and "submit" not in html_content.lower():
            print(f"[DEBUG] Failed to load submit page properly. Response URL: {response.url}")
            print(f"[DEBUG] First 500 chars: {html_content[:500]}")
            return None, None, None
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        csrf_token_input = soup.find('input', {'name': 'csrf_token'})
        if not csrf_token_input:
            print(f"[DEBUG] CSRF token input not found in HTML")
            print(f"[DEBUG] Available form inputs: {[inp.get('name') for inp in soup.find_all('input') if inp.get('name')]}")
            return None, None, None
        
        csrf_token = csrf_token_input['value']
        
        ftaa_match = re.search(r'window\._ftaa\s*=\s*"(.*?)"', html_content)
        bfaa_match = re.search(r'window\._bfaa\s*=\s*"(.*?)"', html_content)
        
        ftaa = ftaa_match.group(1) if ftaa_match else ''
        bfaa = bfaa_match.group(1) if bfaa_match else ''
        
        return csrf_token, ftaa, bfaa
    except Exception as e:
        print(f"Error fetching submission details: {e}")
        return None, None, None

def submit_solution(scraper, contest_id, problem_index, code, csrf_token, ftaa, bfaa, cfg: DictConfig):
    submit_url = f"https://codeforces.com/problemset/submit?adcd1e={cfg.codeforces.adcd1e}&csrf_token={csrf_token}"
    
    payload = {
        'csrf_token': csrf_token,
        'ftaa': ftaa,
        'bfaa': bfaa,
        'action': 'submitSolutionFormSubmitted',
        'submittedProblemCode': f"{contest_id}{problem_index}",
        'programTypeId': cfg.codeforces.program_type_id,
        'source': code,
        'tabSize': '4',
        'sourceFile': '',
        '_tta': cfg.codeforces.tta
    }
    
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'content-type': 'application/x-www-form-urlencoded',
        'referer': 'https://codeforces.com/problemset/submit',
        'origin': 'https://codeforces.com',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        'connection': 'keep-alive',
        'cookie': cfg.codeforces.cookies,
        'priority': 'u=0, i',
        'te': 'trailers',
    }

    try:
        response = scraper.post(submit_url, data=payload, headers=headers, allow_redirects=True)
        
        # Check if submission was successful by looking at the final URL
        # Successful submissions redirect to /problemset/status?my=on or end with /my
        if "/problemset/status" in response.url or response.url.endswith("/my"):
            print(f"Successfully submitted solution for {contest_id}{problem_index}")
        else:
            print(f"Submission failed for {contest_id}{problem_index}. Redirected to: {response.url}")
            #! DEBUGGING START
            soup = BeautifulSoup(response.text, 'lxml')
            # Codeforces usually puts submission errors in a span with this class
            # error_span = soup.find('span', class_='error for__source')
            # if error_span:
            #     error_message = error_span.get_text(strip=True)
            #     print(f"  [DEBUG] Reason: {error_message}")
            # else:
            #     print("  [DEBUG] Could not find a specific error message on the page. The submission might be too frequent or another issue occurred.")
            with open("debug_submission_response.html", "w") as f:
                f.write(soup.prettify())
    except Exception as e:
        print(f"Error submitting solution for {contest_id}{problem_index}: {e}")


def generate_solution(problem_statement, cfg: DictConfig):
    global current_api_key_index
    
    if not problem_statement or "Problem statement not found." in problem_statement:
        return "Could not generate solution: Problem statement is missing."

    api_keys = get_api_keys(cfg)
    if not api_keys:
        return "Error: No API keys found in configuration."
    
    max_attempts = len(api_keys)
    
    for attempt in range(max_attempts):
        try:
            current_key = api_keys[current_api_key_index]
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(cfg.gemini.model_name)
            full_prompt = cfg.gemini.prompt + problem_statement
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a rate limit error
            if 'rate limit' in error_msg or 'quota' in error_msg or '429' in error_msg:
                print(f"Rate limit hit on API key {current_api_key_index + 1}/{len(api_keys)}. Switching to next key...")
                current_api_key_index = (current_api_key_index + 1) % len(api_keys)
                
                # If we've tried all keys, wait a bit before retrying
                if attempt == max_attempts - 1:
                    print(f"All API keys exhausted. Waiting 10 seconds before retry...")
                    time.sleep(10)
                else:
                    time.sleep(1)  # Brief pause before trying next key
            else:
                # Non-rate-limit error, return immediately
                return f"Error generating solution: {e}"
    
    return "Error: All API keys exhausted due to rate limits."

@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    try:
        with open(cfg.files.output_filtered, 'r') as f:
            filtered_problems = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {cfg.files.output_filtered} was not found.")
        return

    # Sort problems by rating (highest to lowest), then by contest ID (highest to lowest)
    filtered_problems.sort(key=lambda p: (p.get('rating', 0), p.get('contestId', 0)), reverse=True)
    
    # Filter problems based on modulus for parallel processing
    modulus = cfg.gemini.modulus
    processes = cfg.gemini.processes
    filtered_problems = [p for i, p in enumerate(filtered_problems[8:]) if i % processes == modulus and p.get('rating', 0) == 1400]
    
    print(f"Process {modulus}/{processes}: Processing {len(filtered_problems)} problems")
    
    submissions_count = 0
    total_problems = len(filtered_problems)
    
    # problem_statements = {}
    for problem_info in filtered_problems:
        contest_id = problem_info['contestId']
        problem_index = problem_info['index']
        print(f"Fetching problem: {contest_id}{problem_index}")
        html_content = get_problem_statement(contest_id, problem_index, cfg.codeforces.cookies)
        statement = parse_problem_statement(html_content)
        
        if statement:
            print(f"Successfully fetched problem {contest_id}{problem_index}")
            print(f"Generating solution for {contest_id}{problem_index}...")
            solution_text = generate_solution(statement, cfg)
            extracted_code = extract_code(solution_text)
            # extracted_code = "test"
            
            if "No C++ code block found" not in extracted_code:
                print(f"--- Submitting Solution for {contest_id}{problem_index} ---")
                scraper = cloudscraper.create_scraper() 
                csrf_token, ftaa, bfaa = get_submission_details(scraper, contest_id, problem_index, cfg.codeforces.cookies)
                # print(f"CSRF: {csrf_token}, FTAA: {ftaa}, BFAA: {bfaa}, TTA: {cfg.codeforces.tta}")
                if csrf_token:
                    submit_solution(scraper, contest_id, problem_index, extracted_code, csrf_token, ftaa, bfaa, cfg)
                    submissions_count += 1
                    print(f"✓ Submitted {submissions_count}/{total_problems} problems so far")
                else:
                    print("Could not submit solution, submission details not found.")
            else:
                print(f"Could not extract code for {contest_id}{problem_index}, skipping submission.")

        else:
            print(f"Could not fetch problem statement for {contest_id}{problem_index}")
        
        # Rate limit: 2 requests per second (0.5 second delay between requests)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
