import cloudscraper
from bs4 import BeautifulSoup
import json
import hydra
from omegaconf import DictConfig
import time
import google.generativeai as genai
import re

def get_problem_statement(contest_id, problem_index, cookie=""):
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}"
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'firefox',
            'platform': 'darwin',
            'mobile': False
        }
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        # 'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': 'https://codeforces.com/problemset',
        'Connection': 'keep-alive',
        'Cookie': cookie,
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
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
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': f"https://codeforces.com/problemset/problem/{contest_id}/{index}",
        'Sec-GPC': '1',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Connection': 'keep-alive',
        'Cookie': cookie,
        'Priority': 'u=0, i',
    }

    try:
        response = scraper.get(submit_page_url, headers=headers)
        response.raise_for_status()
        html_content = response.text
        soup = BeautifulSoup(html_content, 'lxml')
        
        csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
        
        ftaa_match = re.search(r'window\._ftaa\s*=\s*"(.*?)"', html_content)
        bfaa_match = re.search(r'window\._bfaa\s*=\s*"(.*?)"', html_content)
        
        ftaa = ftaa_match.group(1) if ftaa_match else ''
        bfaa = bfaa_match.group(1) if bfaa_match else ''
        
        return csrf_token, ftaa, bfaa
    except Exception as e:
        print(f"Error fetching submission details: {e}")
        return None, None, None

def submit_solution(scraper, contest_id, problem_index, code, csrf_token, ftaa, bfaa, cfg: DictConfig):
    submit_url = f"https://codeforces.com/problemset/submit?csrf_token={csrf_token}"
    payload = {
        'csrf_token': csrf_token,
        'ftaa': ftaa,
        'bfaa': bfaa,
        'action': 'submitSolutionFormSubmitted',
        'submittedProblemCode': f"{contest_id}{problem_index}",
        'programTypeId': cfg.codeforces.program_type_id,
        'source': code,
        'tabSize': '4',
        'sourceFile': ''
    }
    
    headers = {
        'Host': 'codeforces.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        # 'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://codeforces.com/problemset/submit',
        'Origin': 'https://codeforces.com',
        'Sec-GPC': '1',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Connection': 'keep-alive',
        'Cookie': cfg.codeforces.cookies,
        'Priority': 'u=0, i',
    }

    try:
        response = scraper.post(submit_url, data=payload, headers=headers)
        response.raise_for_status()
        if response.url.endswith("/my"):
             print(f"Successfully submitted solution for {contest_id}{problem_index}")
        else:
            print(f"Submission failed for {contest_id}{problem_index}. Redirected to: {response.url}")
            #! DEBUGGING START
            soup = BeautifulSoup(response.text, 'lxml')
            # Codeforces usually puts submission errors in a span with this class
            error_span = soup.find('span', class_='error for__source')
            if error_span:
                error_message = error_span.get_text(strip=True)
                print(f"  [DEBUG] Reason: {error_message}")
            else:
                print("  [DEBUG] Could not find a specific error message on the page. The submission might be too frequent or another issue occurred.")
            #! DEBUGGING END

    except Exception as e:
        print(f"Error submitting solution for {contest_id}{problem_index}: {e}")


def generate_solution(problem_statement, cfg: DictConfig):
    if not problem_statement or "Problem statement not found." in problem_statement:
        return "Could not generate solution: Problem statement is missing."

    try:
        genai.configure(api_key=cfg.gemini.api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')
        full_prompt = cfg.gemini.prompt + problem_statement
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Error generating solution: {e}"

@hydra.main(config_path=".", config_name="config", version_base=None)
def main(cfg: DictConfig):
    try:
        with open(cfg.files.output_filtered, 'r') as f:
            filtered_problems = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file {cfg.files.output_filtered} was not found.")
        return

    # problem_statements = {}
    for problem_info in filtered_problems[:25]:
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
            
            if "No C++ code block found" not in extracted_code:
                print(f"--- Submitting Solution for {contest_id}{problem_index} ---")
                scraper = cloudscraper.create_scraper() 
                csrf_token, ftaa, bfaa = get_submission_details(scraper, contest_id, problem_index, cfg.codeforces.cookies)
                if csrf_token:
                    submit_solution(scraper, contest_id, problem_index, extracted_code, csrf_token, ftaa, bfaa, cfg)
                else:
                    print("Could not submit solution, submission details not found.")
            else:
                print(f"Could not extract code for {contest_id}{problem_index}, skipping submission.")

        else:
            print(f"Could not fetch problem statement for {contest_id}{problem_index}")
        
        # be polite to the server
        time.sleep(1)

if __name__ == "__main__":
    main()
