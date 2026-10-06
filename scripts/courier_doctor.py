#!/usr/bin/env python3
"""
Courier Doctor: Beginner UX tool to diagnose the health of the local Courier Symphony system.
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
import time
import zipfile

def get_app_data_dir():
    pd = os.environ.get("PROGRAMDATA")
    fallback = Path(os.environ.get("COURIER_HOME") or Path.home() / ".courier")
    base = (Path(pd) if pd else fallback) / "CourierWorker"
    return base

def load_config():
    config_path = get_app_data_dir() / "config.json"
    if not config_path.exists():
        config_path = Path(__file__).parent / "windows_worker" / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

def check_ledger():
    state_dir = get_app_data_dir() / "state"
    if not state_dir.exists():
        return False, f"Missing {state_dir}"
    try:
        tasks = list(state_dir.glob("*.json"))
        return True, f"State directory exists. Contains {len(tasks)} JSON files."
    except Exception as e:
        return False, f"Error reading state: {e}"

def check_server():
    config = load_config()
    server = os.environ.get("COURIER_SERVER") or os.environ.get("COURIER_SERVER_URL") or config.get("COURIER_SERVER") or "http://127.0.0.1:8080"
    if server.lower() == "local":
        server = "http://127.0.0.1:8080"
    server = server.rstrip("/")
    try:
        req = urllib.request.Request(f"{server}/health")
        with urllib.request.urlopen(req, timeout=2) as response:
            pass
        return True, f"Server responding at {server}"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return True, f"Server responding at {server} ({e.code})"
        return True, f"Server responding at {server} ({e.code})"
    except Exception as e:
        return False, f"Server unreachable at {server}: {e}"

def check_stuck_tasks():
    state_dir = get_app_data_dir() / "state"
    if not state_dir.exists():
        return True, "No local state to check"
    try:
        current_task_path = state_dir / "current_task.json"
        if not current_task_path.exists():
            return True, "No current task."
        
        with open(current_task_path, "r") as f:
            task = json.load(f)
        
        phase = task.get("worker_phase")
        task_id = task.get("task_id", "unknown")
        
        # We can't really know if it's stuck without timestamps, but we can report its state
        if phase == "STARTED":
            return True, f"Task {task_id} is currently running."
        elif phase == "RESULT_READY":
            return True, f"Task {task_id} is waiting to be delivered."
        elif phase == "RELEASE_PENDING":
            return False, f"Task {task_id} result was rejected and is pending release."
        else:
            return True, f"Task {task_id} is in phase {phase}."
    except Exception as e:
        return False, f"Could not check tasks: {e}"

def redact_api_key(content, key):
    if key and len(key) > 4:
        return content.replace(key, "***REDACTED_API_KEY***")
    return content

def export_diagnostics(out_path):
    app_data = get_app_data_dir()
    config = load_config()
    
    api_key = os.environ.get("COURIER_API_KEY", "").strip()
    if not api_key:
        api_key = str(config.get("COURIER_API_KEY") or "").strip()
        
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Export state files
        state_dir = app_data / "state"
        if state_dir.exists():
            for f in state_dir.glob("*.json"):
                text = f.read_text(encoding="utf-8", errors="replace")
                if api_key:
                    text = redact_api_key(text, api_key)
                zf.writestr(f"state/{f.name}", text)
                
        # Export logs
        log_dir = app_data / "logs"
        if log_dir.exists():
            for f in log_dir.glob("*.log*"):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    if api_key:
                        text = redact_api_key(text, api_key)
                    zf.writestr(f"logs/{f.name}", text)
                except Exception:
                    pass
                    
        # Export config (redacted)
        config_path = app_data / "config.json"
        if config_path.exists():
            text = config_path.read_text(encoding="utf-8", errors="replace")
            if api_key:
                text = redact_api_key(text, api_key)
            zf.writestr("config.json", text)
            
    print(f"Diagnostics bundle exported to {out_path}")

def run_diagnostics():
    print("=== Courier Symphony Doctor ===")
    checks = [
        ("Local State", check_ledger),
        ("Server Health", check_server),
        ("Task Health", check_stuck_tasks)
    ]
    
    all_pass = True
    for name, func in checks:
        print(f"Checking {name}...", end=" ")
        passed, msg = func()
        if passed:
            print(f"[\033[92mOK\033[0m] - {msg}")
        else:
            print(f"[\033[91mFAIL\033[0m] - {msg}")
            all_pass = False
            
    print("===============================")
    if all_pass:
        print("System is healthy. You are good to go!")
    else:
        print("Issues detected. Please resolve the above failures.")
        
    print()
    bundle_path = Path.cwd() / "courier_diagnostics.zip"
    export_diagnostics(bundle_path)

if __name__ == "__main__":
    run_diagnostics()
