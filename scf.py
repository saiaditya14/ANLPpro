#!/usr/bin/env python3
"""
gemini_screenshots_save_tokens.py

Attempts to send screenshots directly as SDK Image/File objects (multiple constructor attempts),
falls back to base64-in-text if necessary, saves raw responses, assembled text, extracted C++,
and token/usage metadata to separate files.

Usage:
  pip install --upgrade google-genai pillow tqdm
  # In PowerShell:
  $env:GENAI_API_KEY = "YOUR_KEY"
  python .\gemini_screenshots_save_tokens.py --model "models/gemini-2.5-flash"

Outputs for each screenshot <name>:
  outputs/<name>.raw.txt       - raw SDK response (string)
  outputs/<name>.response.txt  - assembled textual reply
  outputs/<name>.cpp           - extracted C++ code (heuristic)
  outputs/<name>.tokens.json   - token/usage metadata if found
"""
from __future__ import annotations
import os
import sys
import time
import json
import base64
import re
import traceback
from pathlib import Path
from io import BytesIO
from typing import Optional, Any, Dict, List

try:
    from PIL import Image
except Exception:
    print("Install pillow: pip install pillow")
    raise

try:
    from google import genai
    from google.genai import types as genai_types  # may exist in many SDK versions
except Exception:
    print("Install/upgrade google-genai: pip install --upgrade google-genai")
    raise

# third-party progress bar
try:
    from tqdm import tqdm
except Exception:
    print("Install tqdm: pip install tqdm")
    raise

# ---------- Config ----------
DEFAULT_MODEL = "models/gemini-2.5-pro"
SCREENSHOTS_DIR = Path("screenshots2")
OUTPUT_DIR = Path("outputs")
PROMPT_BASE = (
    "Hey — below is a screenshot. First: say whether the image shows the full problem statement and "
    "all necessary details. If yes, extract constraints, input/output format, and examples. "
    "Then present a solution approach and provide a full C++ solution (single-file)."
)
FOLLOWUP_PROMPT = "please continue thinking and give me final c++ file"
MAX_FOLLOWUPS = 4
PAUSE_BETWEEN_IMAGES = 1.0
MIN_CPP_LINES = 8

# ---------- Helpers ----------
def build_client() -> genai.Client:
    key = os.environ.get("GENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if key:
        return genai.Client(api_key=key)
    return genai.Client()  # ADC fallback

def image_to_pil(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")

def pil_to_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def save_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def assemble_text_from_response(resp: Any) -> str:
    # try several shapes
    try:
        if hasattr(resp, "candidates") and len(resp.candidates) > 0:
            cand = resp.candidates[0]
            # new: cand.content.parts
            if hasattr(cand, "content") and hasattr(cand.content, "parts"):
                out = ""
                for p in cand.content.parts:
                    if hasattr(p, "text") and p.text:
                        out += p.text
                    elif isinstance(p, dict) and "text" in p:
                        out += p["text"]
                    else:
                        out += str(p)
                return out
            if hasattr(cand, "text") and cand.text:
                return cand.text
    except Exception:
        pass
    if hasattr(resp, "text") and isinstance(resp.text, str):
        return resp.text
    try:
        return json.dumps(resp.__dict__, default=str, indent=2)
    except Exception:
        return str(resp)

def extract_code_blocks(text: str) -> List[str]:
    # fenced blocks
    blocks = re.findall(r"```(?:cpp|c\+\+|cpp)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if blocks:
        return [b.strip() for b in blocks]
    blocks2 = re.findall(r"~~~(?:cpp|c\+\+)?\s*\n(.*?)~~~", text, flags=re.DOTALL | re.IGNORECASE)
    if blocks2:
        return [b.strip() for b in blocks2]
    # heuristic contiguous c++ tokens
    lines = text.splitlines()
    cur = []
    cand = []
    for ln in lines:
        if re.search(r"\b(int|long|vector|string|scanf|cout|printf|std::|#include|using namespace|return|main)\b", ln):
            cur.append(ln)
        else:
            if len(cur) >= 3:
                cand.append("\n".join(cur))
            cur = []
    if cur and len(cur) >= 3:
        cand.append("\n".join(cur))
    return [c.strip() for c in cand]

def looks_complete_cpp(code: str) -> bool:
    if not code:
        return False
    lines = [l for l in code.splitlines() if l.strip()]
    if len(lines) >= MIN_CPP_LINES:
        return True
    if re.search(r"\bint\s+main\s*\(", code) and ("return 0;" in code or code.strip().endswith("}")):
        return True
    if code.count("{") > 0 and code.count("{") == code.count("}"):
        return True
    return False

def extract_token_usage_recursive(obj: Any) -> Optional[Dict]:
    """
    Search the response object/dict for common usage/token keys and return a JSON-able object.
    """
    # Convert to dict-like recursively, searching for likely keys
    try:
        # Try common attribute names
        # For many SDKs the response has .candidates[0].content.metadata or .metadata or top-level .usage
        # We'll gather possible fields and return what we find.
        found = {}

        def inspect(o, path="root"):
            if o is None:
                return
            if isinstance(o, dict):
                for k, v in o.items():
                    lk = k.lower()
                    if "token" in lk or "usage" in lk or "count" in lk or "cost" in lk:
                        found_key = path + "." + k
                        found[found_key] = v
                    # recurse
                    inspect(v, path + "." + k)
            elif hasattr(o, "__dict__"):
                d = {}
                try:
                    d = o.__dict__
                except Exception:
                    # fallback: str check
                    pass
                for k, v in d.items():
                    lk = k.lower()
                    if "token" in lk or "usage" in lk or "count" in lk or "cost" in lk:
                        found_key = path + "." + k
                        found[found_key] = v
                    inspect(v, path + "." + k)
            elif isinstance(o, (list, tuple)):
                for i, item in enumerate(o):
                    inspect(item, f"{path}[{i}]")
            else:
                # primitive
                return

        inspect(obj)
        return found if found else None
    except Exception:
        return None

# ---------- Attempts to construct SDK image/file objects ----------
def try_make_sdk_image(genai_types_module, image_bytes: bytes) -> Optional[Any]:
    """
    Try multiple constructor signatures for SDK Image/File types.
    Returns an instance if successful, else None.
    """
    constructors_to_try = []
    # gather candidate classes in module
    candidates = []
    for name in ("Image", "File", "Part", "InputImage"):
        cls = getattr(genai_types_module, name, None)
        if cls:
            candidates.append((name, cls))
    # common kw patterns to attempt
    kw_variants = [
        {"bytes": image_bytes},
        {"data": image_bytes},
        {"content": image_bytes},
        {"b64": base64.b64encode(image_bytes).decode("ascii")},
        {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode("ascii")},
        {"mime_type": "image/png", "b64": base64.b64encode(image_bytes).decode("ascii")},
        {"content_type": "image/png", "content": image_bytes},
    ]
    for name, cls in candidates:
        for kw in kw_variants:
            try:
                inst = cls(**kw)
                print(f"Instantiated SDK type {name} with args {list(kw.keys())}")
                return inst
            except Exception as e:
                # try next
                continue
        # try no-arg then set attrs
        try:
            inst = cls()
            # attempt to set common attributes
            for k, v in kw_variants[0].items():
                try:
                    setattr(inst, k, v)
                except Exception:
                    pass
            # quick sanity check: instance has some attribute
            return inst
        except Exception:
            pass
    return None

# ---------- Core send logic with multiple fallbacks ----------
def send_with_sdk_image(client: genai.Client, model: str, prompt_text: str, image_obj) -> Any:
    # Try basic content list with SDK image obj
    try:
        return client.models.generate_content(model=model, contents=[prompt_text, image_obj])
    except Exception as e:
        # some SDKs accept PIL.Image directly
        try:
            if isinstance(image_obj, Image.Image):
                return client.models.generate_content(model=model, contents=[prompt_text, image_obj])
        except Exception:
            pass
        raise

def send_with_base64_in_text(client: genai.Client, model: str, prompt_text: str, image_bytes: bytes) -> Any:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    full = prompt_text + "\n\n[IMAGE_BASE64]\n" + b64 + "\n\n[END_IMAGE]\n"
    return client.models.generate_content(model=model, contents=[full])

# ---------- Main per-image processing ----------
def process_image_file(client: genai.Client, model: str, path: Path, outdir: Path):
    name = path.stem
    raw_path = outdir / f"{name}.raw.txt"
    resp_path = outdir / f"{name}.response.txt"
    cpp_path = outdir / f"{name}.cpp"
    tokens_path = outdir / f"{name}.tokens.json"

    print(f"\n=== Processing {path} ===")
    pil = image_to_pil(path)
    img_bytes = pil_to_bytes(pil)

    # first try SDK typed image
    used_method = None
    resp = None

    # attempt 1: try to create SDK image object if types module available
    try:
        sdk_img = try_make_sdk_image(genai_types, img_bytes)
        if sdk_img:
            try:
                print("Trying SDK image object path...")
                resp = send_with_sdk_image(client, model, PROMPT_BASE, sdk_img)
                used_method = "sdk_image_object"
            except Exception as e:
                print("SDK-image attempt failed:", e)
                # continue to next attempts
    except Exception as e:
        print("Error while preparing SDK image object:", e)

    # attempt 2: try sending PIL.Image directly in contents (some SDKs accept)
    if resp is None:
        try:
            print("Trying PIL.Image direct path...")
            resp = client.models.generate_content(model=model, contents=[PROMPT_BASE, pil])
            used_method = "pil_image_direct"
        except Exception as e:
            print("PIL-image direct attempt failed:", e)

    # attempt 3: fallback to base64-in-text
    if resp is None:
        try:
            print("Falling back to base64-in-text.")
            resp = send_with_base64_in_text(client, model, PROMPT_BASE, img_bytes)
            used_method = "base64_in_text"
        except Exception as e:
            print("Base64 fallback failed:", e)
            # give up for this image
            trace = traceback.format_exc()
            save_text(raw_path, f"ERROR: all attempts failed for image {name}\n\n{trace}")
            print(f"All send attempts failed for {name}; raw trace saved to {raw_path}")
            return

    # Save raw response
    try:
        raw_dump = json.dumps(resp.__dict__, default=str, indent=2)
    except Exception:
        raw_dump = str(resp)
    save_text(raw_path, raw_dump)

    # assemble textual response and save
    assembled = assemble_text_from_response(resp)
    save_text(resp_path, assembled)

    # extract code & save
    blocks = extract_code_blocks(assembled)
    if not blocks:
        blocks = extract_code_blocks(assembled)  # redundant but safe
    if blocks:
        candidate = sorted(blocks, key=lambda b: len(b.splitlines()), reverse=True)[0]
        save_text(cpp_path, candidate)
        print(f"Saved candidate C++ to {cpp_path} (len {len(candidate.splitlines())} lines).")
    else:
        print("No code block detected in response.")

    # extract token usage heuristically and save
    usage = extract_token_usage_recursive(resp)
    if usage:
        save_text(tokens_path, json.dumps(usage, indent=2, ensure_ascii=False))
        print(f"Saved token/usage metadata to {tokens_path}")
    else:
        # try to search resp.__dict__ for obvious fields
        try:
            maybe = {}
            d = getattr(resp, "__dict__", None)
            if d:
                for k, v in d.items():
                    if isinstance(v, (dict, list)) and ("token" in k.lower() or "usage" in k.lower()):
                        maybe[k] = v
            if maybe:
                save_text(tokens_path, json.dumps(maybe, indent=2, ensure_ascii=False))
                print(f"Saved token-like metadata to {tokens_path}")
            else:
                # still write an empty json noting method
                save_text(tokens_path, json.dumps({"found": False, "used_method": used_method}))
        except Exception:
            save_text(tokens_path, json.dumps({"found": False, "used_method": used_method}))

    print(f"[{name}] done. method={used_method}")

# ---------- Main ----------
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Exact model name from models.list (e.g. models/gemini-2.5-flash)")
    ap.add_argument("--screenshots", default=str(SCREENSHOTS_DIR))
    ap.add_argument("--outdir", default=str(OUTPUT_DIR))
    ap.add_argument("--followups", type=int, default=MAX_FOLLOWUPS)
    args = ap.parse_args()

    model = args.model
    screenshots = Path(args.screenshots)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    client = build_client()
    print("Using model:", model)

    images = sorted([p for p in screenshots.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])
    if not images:
        print("No images found in", screenshots.resolve())
        return

    for img in images:
        try:
            process_image_file(client, model, img, outdir)
            # small sleep to be polite
            time.sleep(PAUSE_BETWEEN_IMAGES)
        except KeyboardInterrupt:
            print("Interrupted by user.")
            return
        except Exception as e:
            print(f"Error processing {img}: {e}")
            traceback.print_exc()
            continue

if __name__ == "__main__":
    main()
