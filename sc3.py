#!/usr/bin/env python3
"""
cf_launch_profile1.py

- Launches Google Chrome using your real Chrome profile "Profile 1".
- Kills running Chrome first (so Playwright can take the profile).
- Opens a Codeforces problem URL, brings the visible browser to front.
- If Cloudflare interstitial appears, asks you to solve it manually.
- Saves debug HTML + screenshot on failure.

EDIT NONE if your Chrome & profile are standard. If not, edit CHROME_EXE or PROFILE_NAME.
"""
from __future__ import annotations
import os
import sys
import time
import subprocess
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ---------- CONFIG ----------
# Set these if your installation differs.
CHROME_EXE_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
PROFILE_NAME = "Profile 2"      # the folder name under "User Data" you want to use
TEST_URL = "https://codeforces.com/contest/2142/problem/D"
OUTDIR = "cf_profile1_run"
# ----------------------------

def find_chrome_exe() -> Optional[str]:
    for p in CHROME_EXE_CANDIDATES:
        if os.path.exists(p):
            return p
    # fallback: check default ProgramFiles env
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    candidate = os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe")
    if os.path.exists(candidate):
        return candidate
    pfx86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    candidate2 = os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe")
    if os.path.exists(candidate2):
        return candidate2
    return None

def chrome_user_data_root() -> str:
    # %LOCALAPPDATA%\Google\Chrome\User Data
    local = os.environ.get("LOCALAPPDATA") or os.path.join("C:\\", "Users", os.getlogin(), "AppData", "Local")
    return os.path.join(local, "Google", "Chrome", "User Data")

def kill_chrome_windows():
    # best-effort termination on Windows
    try:
        if sys.platform.startswith("win"):
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # linux/mac
            subprocess.run(["pkill", "chrome"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def looks_like_cf_interstitial(html: str) -> bool:
    s = html.lower()
    for token in ("just a moment", "verifying you are human", "verify you are human", "checking your browser", "turnstile", "enable javascript and cookies"):
        if token in s:
            return True
    return False

def save_debug(page, prefix: str):
    os.makedirs(OUTDIR, exist_ok=True)
    dbg = os.path.join(OUTDIR, "debug")
    os.makedirs(dbg, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    html_path = os.path.join(dbg, f"{prefix}_{ts}.html")
    pic_path = os.path.join(dbg, f"{prefix}_{ts}.png")
    try:
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(page.content())
        print(f"[debug] wrote {html_path}")
    except Exception as e:
        print("[debug] html save failed:", e)
    try:
        page.screenshot(path=pic_path, full_page=True)
        print(f"[debug] screenshot: {pic_path}")
    except Exception as e:
        print("[debug] screenshot failed:", e)

def extract_statement(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    ps = soup.find("div", class_="problem-statement") or soup.select_one(".problemindexholder .ttypography") or soup.select_one(".problem-text") or soup.select_one(".problem")
    if not ps:
        return soup.get_text("\n", strip=True)[:4000]
    for el in ps(["script", "style"]):
        el.decompose()
    return ps.get_text("\n", strip=True)[:4000]

def main():
    chrome_exe = find_chrome_exe()
    if not chrome_exe:
        print("Chrome executable not found. Edit CHROME_EXE_CANDIDATES to include your path.")
        sys.exit(1)

    user_data_root = chrome_user_data_root()
    profile_dir = os.path.join(user_data_root, PROFILE_NAME)
    if not os.path.isdir(profile_dir):
        print("Profile folder not found:", profile_dir)
        print("Confirm PROFILE_NAME is correct (e.g. 'Default', 'Profile 1', etc).")
        sys.exit(1)

    print("Using Chrome exe:", chrome_exe)
    print("Using profile dir root:", user_data_root)
    print("Using profile:", PROFILE_NAME)
    print("TEST_URL:", TEST_URL)
    print("Killing any running Chrome instances (so Playwright can use the profile).")
    kill_chrome_windows()
    time.sleep(1.2)

    with sync_playwright() as pw:
        try:
            print("[*] Launching persistent Chromium context with your real profile (visible)...")
            context = pw.chromium.launch_persistent_context(
                user_data_dir=user_data_root,            # root USER DATA, not the subfolder
                headless=False,
                executable_path=chrome_exe,
                args=[f"--profile-directory={PROFILE_NAME}", "--start-maximized"],
                viewport={"width": 1280, "height": 900},
                accept_downloads=False,
            )
        except Exception as e:
            print("[ERROR] Failed to launch persistent context. Exception:", e)
            print("Make sure Chrome is fully closed and that you have permissions to that folder.")
            return

        page = context.new_page()
        page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        print("[*] Opening page:", TEST_URL)
        try:
            page.goto(TEST_URL, timeout=180000)
        except PWTimeoutError as e:
            print("[WARN] Navigation timeout:", e)
        except Exception as e:
            print("[WARN] Navigation error:", e)

        # let JS run
        try:
            page.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            pass

        try:
            html = page.content()
        except Exception:
            html = ""

        if looks_like_cf_interstitial(html):
            print("\n[!] Cloudflare interstitial detected. Browser window should be visible now.")
            save_debug(page, "interstitial_before")
            try:
                page.bring_to_front()
                page.evaluate("window.focus()")
            except Exception:
                pass
            print("-> Solve the challenge manually in that browser window. If you can't see it, check taskbar or other monitors.")
            input("Press Enter after you complete the verification in the browser...")

            # wait and re-check
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except Exception:
                pass
            try:
                html2 = page.content()
            except Exception:
                html2 = ""
            if looks_like_cf_interstitial(html2):
                print("[ERROR] Interstitial still present after manual attempt. Saved debug files.")
                save_debug(page, "interstitial_after")
                context.close()
                return
            else:
                print("[+] Cleared. Continuing...")

        # Now attempt to find statement text using simple heuristics
        print("[*] Attempting to extract statement snippet...")
        try:
            html_now = page.content()
            snippet = extract_statement(html_now)
            if snippet and len(snippet.strip()) > 50:
                print("\n[+] Statement snippet:\n")
                print(snippet[:2000])
                save_debug(page, "success")
            else:
                print("[!] Statement not found or too short. Saving debug files.")
                save_debug(page, "no_statement")
        except Exception as e:
            print("[ERROR] while extracting:", e)
            save_debug(page, "extract_error")

        print("\n[*] Done. If extraction succeeded, you can reuse this profile directory for the full scraper.")
        try:
            context.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
