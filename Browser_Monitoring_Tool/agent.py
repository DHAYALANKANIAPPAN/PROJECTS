import os
import sqlite3
import time
import psutil
import socket
import json
from datetime import datetime


SLEEP_INTERVAL = 60  # seconds
SAVE_LOCAL = True  # Save local JSON snapshots


def is_vpn_active():
    """Detect active VPN by checking network adapters."""
    adapters = [n for n in psutil.net_if_addrs().keys()]
    vpn_keywords = ["tap", "tun", "ppp", "wg", "nord", "express", "surf", "vpn"]
    return any(any(k in a.lower() for k in vpn_keywords) for a in adapters)

def detect_browsers():
    """Automatically detect installed browsers and their DB paths."""
    browsers_found = {}
    local = os.getenv("LOCALAPPDATA")
    appdata = os.getenv("APPDATA")

    # Chrome
    chrome_path = os.path.join(local, "Google\\Chrome\\User Data\\Default\\History")
    if os.path.exists(chrome_path):
        browsers_found["Chrome"] = chrome_path

    # Edge
    edge_path = os.path.join(local, "Microsoft\\Edge\\User Data\\Default\\History")
    if os.path.exists(edge_path):
        browsers_found["Edge"] = edge_path

    # Brave
    brave_path = os.path.join(local, "BraveSoftware\\Brave-Browser\\User Data\\Default\\History")
    if os.path.exists(brave_path):
        browsers_found["Brave"] = brave_path

    # Firefox
    firefox_root = os.path.join(appdata, "Mozilla\\Firefox\\Profiles")
    if os.path.exists(firefox_root):
        profiles = [os.path.join(firefox_root, p, "places.sqlite")
                    for p in os.listdir(firefox_root)
                    if os.path.isdir(os.path.join(firefox_root, p))]
        for idx, db in enumerate(profiles):
            browsers_found[f"Firefox_{idx+1}"] = db

    return browsers_found

def extract_history(db_path, browser):
    """Copy and extract URLs from SQLite browser database."""
    temp_path = f"{browser}_temp.db"
    data = []
    try:
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, temp_path)
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 50"
            )
            rows = cursor.fetchall()
            conn.close()
            os.remove(temp_path)

            for r in rows:
                data.append({
                    "browser": browser,
                    "url": r[0],
                    "title": r[1],
                    "timestamp": datetime.now().isoformat()
                })
    except Exception as e:
        print(f"[{browser}] Error: {e}")
    return data

def save_snapshot(data):
    """Save extracted data locally as JSON."""
    filename = f"history_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[+] Snapshot saved: {filename}")

def main():
    print("=== Browser History Agent Started ===")
    while True:
        if is_vpn_active():
            print("[!] VPN detected — data extraction skipped.")
        else:
            all_data = []
            browsers_to_extract = detect_browsers()
            for browser, path in browsers_to_extract.items():
                all_data += extract_history(path, browser)

            if all_data:
                print(f"[+] Extracted {len(all_data)} records.")
                if SAVE_LOCAL:
                    save_snapshot(all_data)
            else:
                print("[!] No data extracted.")

        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    main()
