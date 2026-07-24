# Required packages: pip install requests psutil scikit-learn joblib

import os
import sqlite3
import time
import socket
import requests
import shutil
from datetime import datetime, timedelta
import json
import pathlib
import subprocess
import psutil

# --------- CONFIG ----------
SERVER_URL = "https://tool-jc5z.onrender.com/upload"  # ✅ Your actual URL
AUTH_USER = "admin"
AUTH_PASS = "myStrongPassword123"  # ✅ Must match your server

SLEEP_INTERVAL = 60  # 1 minute for real-time updates
LAB_NAME = os.getenv("LAB_NAME", "Lab-1")
SYSTEM_NAME = socket.gethostname()
ALLOWED_DOMAINS = ["110.172.151.102", "your-portal-domain.com"]

VECTOR_FILE = "vectorizer.pkl"
MODEL_FILE = "category_model.pkl"

# ---------- ML SAMPLE DATA ----------
SAMPLE_TEXTS = [
    "facebook.com","youtube.com/watch?v=abc123","instagram.com/user/profile",
    "stackoverflow.com/questions/12345","github.com/openai/gpt","netflix.com/title/6789",
    "google.com/search?q=machine+learning","docs.python.org/3/tutorial/","linkedin.com/in/developer",
    "gmail.com/mail/u/0","zoom.us/j/123456789","twitter.com/home","reddit.com/r/technology/",
    "spotify.com/playlist/abcd","coursera.org/learn/python","medium.com/@techstories",
    "hulu.com/watch/series","dropbox.com/s/files","slack.com/workspace","bbc.com/news/world",
    "pinterest.com/ideas/","amazon.in/product/B09XYZ","office.com/login","telegram.me/channel",
    "twitch.tv/livegame","openai.com/research","disneyplus.com/movies/","flipkart.com/viewcart",
    "nytimes.com/section/technology","quora.com/topic/AI","wikipedia.org/wiki/Python"
]

SAMPLE_LABELS = [
    "Social","Entertainment","Social","Technical","Technical","Entertainment",
    "Search","Technical","Work","Communication","Communication","Social","Social",
    "Entertainment","Education","Blog","Entertainment","Work","Work","News",
    "Social","E-commerce","Work","Communication","Entertainment","Technical",
    "Entertainment","E-commerce","News","Knowledge","Education"
]

# ---------- ML TRAINING ----------
def train_or_load_model():
    try:
        import joblib
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.ensemble import RandomForestClassifier

        if os.path.exists(VECTOR_FILE) and os.path.exists(MODEL_FILE):
            vectorizer = joblib.load(VECTOR_FILE)
            clf = joblib.load(MODEL_FILE)
            print("[Agent ML] Loaded existing model.")
        else:
            print("[Agent ML] Training new model...")
            vectorizer = TfidfVectorizer(ngram_range=(1,2), max_features=1000)
            X = vectorizer.fit_transform(SAMPLE_TEXTS)
            clf = RandomForestClassifier(n_estimators=50, random_state=42)
            clf.fit(X, SAMPLE_LABELS)
            joblib.dump(vectorizer, VECTOR_FILE)
            joblib.dump(clf, MODEL_FILE)
            print("[Agent ML] Model trained successfully.")
        return vectorizer, clf
    except Exception as e:
        print(f"[Agent ML] Error in model setup: {e}")
        return None, None

VECTOR, MODEL = train_or_load_model()

def classify_text(text):
    try:
        if not text:
            return "Uncategorized"
        if "110.172.151.102" in text:
            return "Portal"
        if VECTOR is None or MODEL is None:
            return "Uncategorized"
        X = VECTOR.transform([text])
        return MODEL.predict(X)[0]
    except Exception as e:
        print(f"[Agent ML] Prediction error: {e}")
        return "Uncategorized"

# ---------- VPN DETECTION ----------
def detect_and_disable_vpn_adapters():
    """Detect VPN adapters and disable them if active."""
    try:
        ps_cmd = (
            "Get-NetAdapter | Where-Object {($_.Status -eq 'Up') -and "
            "($_.Name -match 'VPN|vpn' -or $_.InterfaceDescription -match 'TAP|OpenVPN|WireGuard|Proton|Nord')} | "
            "Select-Object -ExpandProperty Name"
        )
        result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=30)
        active_vpns = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        
        if active_vpns:
            for adapter in active_vpns:
                try:
                    disable_cmd = f"Disable-NetAdapter -Name '{adapter}' -Confirm:$false"
                    subprocess.run(["powershell", "-Command", disable_cmd], capture_output=True, timeout=30)
                    print(f"[Agent VPN] Disabled VPN adapter: {adapter}")
                except subprocess.TimeoutExpired:
                    print(f"[Agent VPN] Timeout disabling adapter: {adapter}")
                
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "system": SYSTEM_NAME,
                "lab": LAB_NAME,
                "vpn_disabled": active_vpns
            }
            with open("vpn_log.json", "a", encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + "\n")
        else:
            print("[Agent VPN] No active VPN adapters found.")
    except Exception as e:
        print(f"[Agent VPN] Error detecting/disabling VPN: {e}")

# ---------- BROWSER DETECTION ----------
def detect_browsers_all_users():
    users_dir = pathlib.Path("C:/Users")
    browsers_found = {}
    
    if not users_dir.exists():
        print("[Agent] Users directory not found")
        return browsers_found

    for user_folder in users_dir.iterdir():
        if not user_folder.is_dir() or user_folder.name in ["Default", "Public", "All Users"]:
            continue
            
        user_name = user_folder.name
        local = user_folder / "AppData/Local"
        appdata = user_folder / "AppData/Roaming"

        # Chrome, Edge, Brave
        for browser_name, subpath in {
            "Chrome": "Google/Chrome/User Data",
            "Edge": "Microsoft/Edge/User Data", 
            "Brave": "BraveSoftware/Brave-Browser/User Data"
        }.items():
            base_path = local / subpath
            if base_path.exists():
                try:
                    for profile in base_path.iterdir():
                        if profile.is_dir() and profile.name not in ["System Profile", "Guest Profile"]:
                            hist = profile / "History"
                            if hist.exists():
                                key = f"{browser_name}_{user_name}_{profile.name}"
                                browsers_found[key] = str(hist)
                except PermissionError:
                    print(f"[Agent] Permission denied accessing {browser_name} for user {user_name}")

        # Firefox
        firefox_path = appdata / "Mozilla/Firefox/Profiles"
        if firefox_path.exists():
            try:
                for profile in firefox_path.iterdir():
                    if profile.is_dir():
                        places = profile / "places.sqlite"
                        if places.exists():
                            key = f"Firefox_{user_name}_{profile.name}"
                            browsers_found[key] = str(places)
            except PermissionError:
                print(f"[Agent] Permission denied accessing Firefox for user {user_name}")
    
    print(f"[Agent] Found {len(browsers_found)} browser profiles")
    return browsers_found

# ---------- HISTORY EXTRACTION ----------
def extract_history(db_path, browser_name):
    temp = f"temp_{hash(db_path) & 0xFFFFFFFF}.db"
    out = []
    
    try:
        # Copy database to avoid locks
        shutil.copy2(db_path, temp)
        
        conn = sqlite3.connect(temp)
        cur = conn.cursor()
        
        # Get today's date for filtering - use wider range to catch recent activity
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # Try Chrome/Edge/Brave schema first
        try:
            # Get more records and filter by date in Python for better control
            cur.execute("SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 1000")
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            # Try Firefox schema
            try:
                cur.execute("SELECT url, title, last_visit_date FROM moz_places ORDER BY last_visit_date DESC LIMIT 1000")
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                rows = []
        
        conn.close()
        
        today_count = 0
        total_count = 0
        
        for r in rows:
            if not r or len(r) < 3:
                continue
                
            url = r[0] or ""
            title = r[1] or ""
            
            if not url.strip():
                continue
            
            total_count += 1
                
            # Convert Chrome timestamp to ISO format if needed
            record_date = None
            try:
                if r[2] and r[2] > 10000000000000000:  # Chrome timestamp
                    ts = datetime(1601, 1, 1) + timedelta(microseconds=r[2])
                    record_date = ts.date()
                    timestamp = ts.isoformat()
                elif r[2] and r[2] > 0:  # Firefox timestamp (milliseconds since epoch)
                    ts = datetime(1970, 1, 1) + timedelta(milliseconds=r[2])
                    record_date = ts.date()
                    timestamp = ts.isoformat()
                else:
                    record_date = datetime.now().date()
                    timestamp = datetime.utcnow().isoformat()
            except Exception as time_err:
                print(f"[Agent] Time conversion error: {time_err}")
                record_date = datetime.now().date()
                timestamp = datetime.utcnow().isoformat()
            
            # ✅ MODIFIED: Send data from today AND yesterday to ensure we catch recent activity
            if record_date and record_date < yesterday:
                continue  # Skip data older than yesterday
            
            today_count += 1
            
            category = classify_text(f"{title} {url}")
            flagged = 0
            
            # Check if domain is allowed
            if not any(domain in url for domain in ALLOWED_DOMAINS):
                # Simple heuristic for suspicious sites
                suspicious_keywords = ['proxy', 'vpn', 'unblock', 'bypass', 'anonym']
                if any(keyword in url.lower() for keyword in suspicious_keywords):
                    flagged = 1
            
            # ✅ FIXED: Map to correct field names expected by the server/dashboard
            out.append({
                "id": f"{browser_name}_{hash(url) & 0xFFFFFFFF}",  # Add unique ID
                "lab_name": LAB_NAME,  # Must match dashboard field
                "system_name": SYSTEM_NAME,  # Must match dashboard field
                "user_name": browser_name.split('_')[1] if '_' in browser_name else "Unknown",  # Extract username from browser key
                "category": category,
                "url": url[:500],
                "timestamp": timestamp,
                "flagged": flagged,
                # Keep original for debugging
                "browser": browser_name,
                "title": title[:500]
            })
            
        print(f"[Agent] {browser_name}: {today_count}/{total_count} recent records")
            
    except Exception as e:
        print(f"[Agent] {browser_name} extraction error: {e}")
    finally:
        # Cleanup temp file
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except:
            pass
    
    return out

# ---------- BUFFER SYSTEM ----------
BUFFER_FILE = "unsent_buffer.json"

def load_buffer():
    if os.path.exists(BUFFER_FILE):
        try:
            with open(BUFFER_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Agent] Error loading buffer: {e}")
            return []
    return []

def save_buffer(data):
    try:
        with open(BUFFER_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[Agent] Saved {len(data)} records to buffer")
    except Exception as e:
        print(f"[Agent] Error saving buffer: {e}")

# ---------- UPLOAD SYSTEM ----------
def test_visibility():
    """Test if data is visible in dashboard"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        test_url = f"https://tool-jc5z.onrender.com/data?date={today}&limit=5"
        
        response = requests.get(test_url, auth=(AUTH_USER, AUTH_PASS), timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"[Agent] 📊 Dashboard shows {len(data)} records for today")
            if data:
                latest_time = data[0].get('timestamp', 'Unknown')[:19]
                print(f"[Agent] 📅 Latest record: {latest_time}")
                # Print sample record to verify structure
                sample = data[0]
                print(f"[Agent] 🔍 Sample record: Lab={sample.get('lab_name')}, System={sample.get('system_name')}, User={sample.get('user_name')}")
            else:
                print("[Agent] ❌ No records visible in dashboard")
        else:
            print(f"[Agent] ❌ Server returned {response.status_code}")
    except Exception as e:
        print(f"[Agent] ❌ Visibility test failed: {e}")

def send_to_server(records, chunk_size=50):
    if not records:
        print("[Agent] No records to send")
        return
        
    # Filter buffer to only include recent data (today and yesterday)
    today = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    buffered_records = load_buffer()
    
    # Filter buffer to keep only recent data
    filtered_buffer = [r for r in buffered_records 
                      if r.get('timestamp', '').startswith(today) or 
                         r.get('timestamp', '').startswith(yesterday)]
    
    # If we filtered out old buffer data, save the cleaned buffer
    if len(filtered_buffer) != len(buffered_records):
        print(f"[Agent] Cleaned buffer: removed {len(buffered_records) - len(filtered_buffer)} old records")
        save_buffer(filtered_buffer)
    
    all_records = filtered_buffer + records
    total = len(all_records)
    sent = 0
    
    if total == 0:
        print("[Agent] No records to send after filtering")
        return
        
    print(f"[Agent] Attempting to send {total} records in chunks of {chunk_size}")
    
    while sent < total:
        chunk = all_records[sent:sent + chunk_size]
        try:
            print(f"[Agent] Sending chunk {sent//chunk_size + 1}...")
            
            # Debug: Print first record structure
            if sent == 0 and chunk:
                print(f"[Agent] 🧪 First record structure:")
                print(f"  Lab: {chunk[0].get('lab_name')}")
                print(f"  System: {chunk[0].get('system_name')}")
                print(f"  User: {chunk[0].get('user_name')}")
                print(f"  URL: {chunk[0].get('url')[:50]}...")
                print(f"  Timestamp: {chunk[0].get('timestamp')}")
            
            response = requests.post(
                SERVER_URL,
                json=chunk,
                timeout=45,
                auth=(AUTH_USER, AUTH_PASS),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print(f"[Agent] ✅ Successfully sent {len(chunk)} records")
                sent += len(chunk)
                
                # Quick test to verify data is visible every few chunks
                if sent % 100 == 0:
                    test_visibility()
                    
            else:
                print(f"[Agent] ❌ Server error {response.status_code}: {response.text}")
                save_buffer(all_records[sent:])
                return
                
        except requests.exceptions.Timeout:
            print(f"[Agent] ⚠ Timeout, reducing chunk size...")
            chunk_size = max(20, chunk_size // 2)
            save_buffer(all_records[sent:])
            return
        except requests.exceptions.ConnectionError:
            print(f"[Agent] ❌ Connection failed - server unreachable")
            save_buffer(all_records[sent:])
            return
        except Exception as e:
            print(f"[Agent] ❌ Upload error: {e}")
            save_buffer(all_records[sent:])
            return
    
    # Clear buffer if all sent successfully
    if os.path.exists(BUFFER_FILE):
        os.remove(BUFFER_FILE)
        print("[Agent] ✅ Buffer cleared")
    
    # Final visibility test
    print("[Agent] 🎯 Final visibility test...")
    test_visibility()

# ---------- TEST DATA GENERATION ----------
def generate_test_data():
    """Generate test data to verify the pipeline is working"""
    test_records = []
    for i in range(5):
        test_records.append({
            "id": f"test_{int(time.time())}_{i}",
            "lab_name": LAB_NAME,
            "system_name": SYSTEM_NAME,
            "user_name": "TestUser",
            "category": "Test",
            "url": f"http://example.com/test{i}",
            "timestamp": datetime.utcnow().isoformat(),
            "flagged": 0,
            "browser": "TestBrowser",
            "title": f"Test Page {i}"
        })
    return test_records

# ---------- MAIN LOOP ----------
def main():
    print(f"=== Agent Started ===\nSystem: {SYSTEM_NAME}\nLab: {LAB_NAME}")
    print(f"Target: {SERVER_URL}")
    print(f"📅 MODE: Sending recent data (today and yesterday)")
    
    # Initial visibility test
    print("[Agent] 🔍 Initial dashboard visibility test...")
    test_visibility()
    
    # Send test data first to verify the pipeline
    print("[Agent] 🧪 Sending test data to verify pipeline...")
    test_data = generate_test_data()
    send_to_server(test_data)
    
    iteration = 0
    while True:
        try:
            print(f"\n--- Iteration {iteration} ---")
            
            # Run VPN detection every 10 iterations
            if iteration % 10 == 0:
                detect_and_disable_vpn_adapters()
            
            # Collect browser data
            browsers = detect_browsers_all_users()
            aggregated = []
            
            if not browsers:
                print("[Agent] ⚠ No browsers detected, checking if this is expected...")
            else:
                for bname, path in browsers.items():
                    records = extract_history(path, bname)
                    aggregated.extend(records)
                    print(f"[Agent] Extracted {len(records)} recent records from {bname}")
            
            print(f"[Agent] Total recent records collected: {len(aggregated)}")
            
            # Send to server
            if aggregated:
                send_to_server(aggregated)
            else:
                print("[Agent] No new recent records to send")
                # Check if we should send test data again
                if iteration % 5 == 0:  # Every 5 iterations
                    print("[Agent] 🧪 Sending test data to keep pipeline active...")
                    test_data = generate_test_data()
                    send_to_server(test_data)
            
            # Check buffer size
            buffer_size = len(load_buffer())
            if buffer_size > 0:
                print(f"[Agent] ⚠ Unsent recent records in buffer: {buffer_size}")
            
            iteration += 1
            print(f"[Agent] Waiting {SLEEP_INTERVAL} seconds...")
            time.sleep(SLEEP_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n[Agent] Stopped by user")
            break
        except Exception as e:
            print(f"[Agent] Error in main loop: {e}")
            time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    main()
