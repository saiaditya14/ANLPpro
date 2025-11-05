#!/usr/bin/env python3
"""
gemini_cf_textgen.py
--------------------
Reads a JSON of Codeforces problems, fetches statements using real browser headers,
and calls Gemini three times per problem:

  1. With samples      → outputs_with_samples/
  2. Without samples   → outputs_without_samples/
  3. Fudged samples    → outputs_fudged_samples/

Each variant saves:
  <contestId>_<index>.response.txt   (raw Gemini reply)
  <contestId>_<index>.cpp            (extracted C++ block)
  <contestId>_<index>.tokens.json    (usage/token metadata)

Usage:
  pip install --upgrade google-genai cloudscraper beautifulsoup4 lxml tqdm
  export GENAI_API_KEY="YOUR_KEY"
  python gemini_cf_textgen.py problems.json --model "models/gemini-2.5-pro"
"""

import os, json, re, base64, time, random, traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
from tqdm import tqdm
import cloudscraper
from bs4 import BeautifulSoup

# ---------- Gemini ----------
try:
    from google import genai
except Exception:
    raise SystemExit("Install google-genai: pip install --upgrade google-genai")

DEFAULT_MODEL = "models/gemini-2.5-pro"
PROMPT_BASE = (
    "Below is a Codeforces problem statement.\n"
    "Please understand it and produce a full working C++17 solution."
    " Print only the final code in triple backticks:\n"
    "```cpp\n<code>\n```\n"
)
PAUSE = 1.5
MIN_CPP_LINES = 8


# ---------- Scraper (your headers logic) ----------
def create_scraper_with_spoof():
    return cloudscraper.create_scraper(
        browser={"browser": "firefox", "platform": "darwin", "mobile": False}
    )

def fetch_problem_html(contestId: int, index: str, cookie: str = "") -> Optional[str]:
    url = f"https://codeforces.com/problemset/problem/{contestId}/{index}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
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
    scraper = create_scraper_with_spoof()
    try:
        r = scraper.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


# ---------- Parse statement & samples ----------
def extract_statement(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.select_one(".problem-statement .title") or soup.select_one(".title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    stmt_block = soup.select_one(".problem-statement") or soup.body
    stmt_copy = BeautifulSoup(str(stmt_block), "lxml")
    for el in stmt_copy.select(".input, .output, .sample-tests, .note"):
        el.decompose()
    statement = stmt_copy.get_text("\n", strip=True)

    samples = []
    if stmt_block.select(".sample-tests"):
        for s in stmt_block.select(".sample-tests .sample-test"):
            inp = s.select_one(".input pre")
            out = s.select_one(".output pre")
            samples.append({
                "input": inp.get_text("\n", strip=False) if inp else "",
                "output": out.get_text("\n", strip=False) if out else ""
            })
    return {"title": title, "statement": statement, "samples": samples}


# ---------- Fudging ----------
def fudge_sample(text: str, rng: random.Random) -> str:
    def shift_num(m): return str(int(m.group(0)) + rng.choice([-1, 1]))
    return re.sub(r"-?\d+", shift_num, text)


# ---------- Gemini helpers ----------
def build_client() -> genai.Client:
    key = os.environ.get("GENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if key:
        return genai.Client(api_key=key)
    return genai.Client()

def assemble_text(resp: Any) -> str:
    try:
        if hasattr(resp, "candidates") and resp.candidates:
            cand = resp.candidates[0]
            if hasattr(cand, "content") and getattr(cand.content, "parts", None):
                out = ""
                for p in cand.content.parts:
                    if hasattr(p, "text") and p.text:
                        out += p.text
                    elif isinstance(p, dict) and "text" in p:
                        out += p["text"]
                return out
            if hasattr(cand, "text") and cand.text:
                return cand.text
    except Exception:
        pass
    return str(resp)

def extract_code_blocks(text: str) -> List[str]:
    blocks = re.findall(r"```(?:cpp|c\+\+)?\s*\n(.*?)```", text, flags=re.S|re.I)
    if blocks: return [b.strip() for b in blocks]
    lines = text.splitlines()
    cur, cand = [], []
    for ln in lines:
        if re.search(r"\b(int|long|vector|string|main|#include)\b", ln):
            cur.append(ln)
        else:
            if len(cur) >= 3: cand.append("\n".join(cur)); cur=[]
    if len(cur)>=3: cand.append("\n".join(cur))
    return cand

def save_text(path: Path, text: str): 
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def extract_token_usage(resp: Any) -> Dict[str, Any]:
    found = {}
    def inspect(o, path="root"):
        if o is None: return
        if isinstance(o, dict):
            for k,v in o.items():
                if any(x in k.lower() for x in ["token","usage","count"]): found[path+"."+k]=v
                inspect(v, path+"."+k)
        elif hasattr(o,"__dict__"): inspect(o.__dict__, path)
        elif isinstance(o,(list,tuple)):
            for i,it in enumerate(o): inspect(it,f"{path}[{i}]")
    inspect(resp)
    return found


# ---------- Main Gemini generation ----------
def generate_variant(client, model, prob, variant, rng):
    cid, idx = prob["contestId"], prob["index"]
    base_name = f"{cid}_{idx}"
    if variant=="with": outdir = Path("outputs_with_samples")
    elif variant=="without": outdir = Path("outputs_without_samples")
    else: outdir = Path("outputs_fudged_samples")
    outdir.mkdir(exist_ok=True)

    stmt, samples = prob["statement"], prob["samples"]
    sample_txt = ""
    if samples:
        sample_txt = "\n\nSamples:\n" + "\n".join(
            f"Input:\n{(fudge_sample(s['input'], rng) if variant=='fudged' else s['input'])}\nOutput:\n{s['output']}"
            for s in samples
        )

    instruction = {
        "with": "You may use these samples as part of your reasoning.",
        "without": "Do NOT use or assume any sample cases.",
        "fudged": "Samples below are intentionally WRONG or misleading; produce the correct code anyway."
    }[variant]

    prompt = f"{PROMPT_BASE}\n{instruction}\n\nProblem:\n{stmt}{sample_txt}"

    try:
        resp = client.models.generate_content(model=model, contents=[prompt])
    except Exception as e:
        save_text(outdir/f"{base_name}.response.txt", f"ERROR: {e}")
        return

    txt = assemble_text(resp)
    save_text(outdir/f"{base_name}.response.txt", txt)

    blocks = extract_code_blocks(txt)
    if blocks:
        code = max(blocks, key=lambda b: len(b.splitlines()))
        save_text(outdir/f"{base_name}.cpp", code)
    usage = extract_token_usage(resp)
    if usage:
        save_text(outdir/f"{base_name}.tokens.json", json.dumps(usage, indent=2, ensure_ascii=False))
    print(f"Saved {variant} for {base_name}")


# ---------- Main ----------
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file", help="JSON list of problems")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--cookie", default="")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    client = build_client()

    for prob in tqdm(data, desc="problems"):
        cid, idx = prob["contestId"], prob["index"]
        html = fetch_problem_html(cid, idx, args.cookie)
        if not html: continue
        info = extract_statement(html)
        prob.update(info)
        for variant in ["with", "without", "fudged"]:
            try:
                generate_variant(client, args.model, prob, variant, rng)
                time.sleep(PAUSE)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"Error {cid}{idx} {variant}:", e)
                traceback.print_exc()

if __name__ == "__main__":
    main()
