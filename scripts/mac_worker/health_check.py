import json, subprocess, os, urllib.request, time
from pathlib import Path

BASE_DIR = Path(__file__).parent
STATE_DIR = BASE_DIR / "state"

def run():
    print("=== Mac Worker Health Check ===")
    
    # 1. launchd status
    try:
        out = subprocess.check_output(["launchctl", "list"]).decode()
        if "com.courier.mac_worker" in out:
            print("launchd worker status: RUNNING")
        else:
            print("launchd worker status: STOPPED")
    except Exception as e:
        print(f"launchd check failed: {e}")
        
    # 2. Keychain availability
    try:
        subprocess.check_output(["security", "find-generic-password", "-a", "courier_worker", "-s", "courier_server_url"], stderr=subprocess.DEVNULL)
        print("Keychain credentials: FOUND")
    except:
        print("Keychain credentials: NOT FOUND (or inaccessible)")
        
    # 3. Pending checkpoints
    print(f"Pending Task Checkpoint: {'EXISTS' if (STATE_DIR / 'current_task.json').exists() else 'NONE'}")
    print(f"Pending Result Checkpoint: {'EXISTS' if (STATE_DIR / 'current_result.json').exists() else 'NONE'}")
    
    # 4. Capabilities
    import shutil
    caps = ["macos", "linux"]
    if shutil.which("agy") or shutil.which("agy", path="/Users/user/.local/bin:/usr/local/bin:/opt/homebrew/bin"):
        caps.append("antigravity")
    if shutil.which("gh") and "copilot" in subprocess.getoutput("gh extension list"):
        caps.append("copilot")
    print(f"Available Providers: {', '.join(caps)}")
    
if __name__ == "__main__":
    run()
