#!/usr/bin/env python3
"""
open_cf_profile.py

Launch Chrome with a profile and URL.
Optional: take a backend screenshot (whole screen).

Usage:
    python open_cf_profile.py --profile "Profile 2" --url "https://codeforces.com" --screenshot out.png
"""
import os, sys, subprocess, argparse, shutil, time

def find_chrome_exe(cli_path=None):
    DEFAULT_WINDOWS_PATHS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    DEFAULT_MAC_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    DEFAULT_LINUX_NAMES = ["google-chrome-stable", "google-chrome", "chrome", "chromium-browser", "chromium"]

    if cli_path and os.path.exists(cli_path):
        return cli_path
    for n in DEFAULT_LINUX_NAMES:
        p = shutil.which(n)
        if p: return p
    if sys.platform.startswith("win"):
        for p in DEFAULT_WINDOWS_PATHS:
            if os.path.exists(p): return p
    if sys.platform.startswith("darwin") and os.path.exists(DEFAULT_MAC_PATH):
        return DEFAULT_MAC_PATH
    return None

def build_cmd(chrome_exe, profile, url, new_window):
    cmd = [chrome_exe, f"--profile-directory={profile}",
           "--no-first-run", "--no-default-browser-check"]
    if new_window: cmd.append("--new-window")
    cmd.append(url)
    return cmd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--new-window", action="store_true")
    ap.add_argument("--screenshot", help="Path to PNG to save screen capture.")
    args = ap.parse_args()

    chrome_exe = find_chrome_exe(args.chrome)
    if not chrome_exe:
        print("Chrome not found")
        sys.exit(1)

    cmd = build_cmd(chrome_exe, args.profile, args.url, args.new_window)
    subprocess.Popen(cmd)

    if args.screenshot:
        # give Chrome a few seconds to render
        time.sleep(5)
        try:
            import pyautogui
        except ImportError:
            print("Install pyautogui: pip install pyautogui")
            sys.exit(1)
        img = pyautogui.screenshot()
        img.save(args.screenshot)
        print(f"Screenshot saved to {args.screenshot}")

if __name__ == "__main__":
    main()
