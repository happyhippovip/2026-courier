import json, subprocess, os, urllib.request, time
from pathlib import Path

BASE_DIR = Path(__file__).parent
STATE_DIR = Path(os.environ.get("COURIER_WORKER_STATE_DIR") or (BASE_DIR / "state"))

def run():
    print("=== Mac Worker Health Check ===")
    
    # 1. launchd status
    try:
        out = subprocess.check_output(["launchctl", "list"], timeout=5).decode()
        if "com.courier.mac_worker" in out:
            print("launchd worker status: RUNNING")
        else:
            print("launchd worker status: STOPPED")
    except Exception as e:
        print(f"launchd check failed: {e}")
        
    # 2. Keychain availability
    credentials = {}
    for name in ("courier_server_url", "courier_api_key"):
        try:
            subprocess.check_output(
                ["security", "find-generic-password", "-a", "courier_worker", "-s", name],
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            credentials[name] = True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            credentials[name] = False
    if all(credentials.values()):
        print("Keychain credentials: FOUND")
    else:
        missing = ", ".join(name for name, found in credentials.items() if not found)
        print(f"Keychain credentials: INCOMPLETE ({missing} missing or inaccessible)")
        
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
