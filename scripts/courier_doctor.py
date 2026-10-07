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
    import sys
    if os.environ.get("COURIER_HOME"):
        return Path(os.environ["COURIER_HOME"])
    
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Courier"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Courier"
    else:
        return Path.home() / ".courier"

def load_config():
    config_path = get_app_data_dir() / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

def check_ledger():
    db_path = get_app_data_dir() / "courier.db"
    if not db_path.exists():
        return False, f"Missing ledger at {db_path}"
    
    try:
        # We don't import sqlite3 here strictly but we could
        import sqlite3
        conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
        cursor = conn.execute("SELECT seq FROM events ORDER BY seq DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        seq = row[0] if row else 0
        return True, f"Ledger exists. {seq} events recorded."
    except Exception as e:
        return False, f"Error reading ledger: {e}"

def _controller_base_url(config):
    """Resolve the V1 controller URL from env or install config."""
    server = (os.environ.get("COURIER_SERVER") or os.environ.get("COURIER_SERVER_URL")
              or config.get("COURIER_SERVER"))
    if server:
        if str(server).lower() == "local":
            return "http://127.0.0.1:8080"
        return str(server).rstrip("/")
    port = config.get("COURIER_CONTROLLER_PORT", 8080)
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 8080
    return f"http://127.0.0.1:{port}"


def _read_controller_token(app_data):
    token_file = app_data / "run" / "controller.token"
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token or None


def check_server():
    config = load_config()
    server = _controller_base_url(config)
    token = _read_controller_token(get_app_data_dir())
    if not token:
        return False, "Missing controller token (run/controller.token); cannot check V1 controller health"
    try:
        req = urllib.request.Request(
            f"{server}/v1/health",
            headers={"X-Courier-Token": token},
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, f"Controller rejected the install token at {server} (401)"
        return False, f"Controller health check failed at {server} ({e.code})"
    except Exception as e:
        return False, f"Controller unreachable at {server}: {e}"
    mode = payload.get("mode")
    if mode == "degraded_readonly":
        return False, f"Controller at {server} is in safe mode (degraded_readonly)"
    if mode != "normal":
        return False, f"Controller at {server} reports unexpected mode: {mode!r}"
    head = payload.get("head_seq", "?")
    return True, f"Controller healthy at {server} (head_seq={head})"

def check_stuck_tasks():
    # In V1 we could query the DB, but without pulling in full courier_core
    # we just report "Check ledger via `courier status`" for now.
    db_path = get_app_data_dir() / "courier.db"
    if not db_path.exists():
        return True, "No local state to check"
    return True, "Use `python -m courier_core.cli status` to check tasks."

def redact_secrets(content, secrets):
    for secret in secrets:
        if secret and len(secret) > 4:
            content = content.replace(secret, "***REDACTED***")
    return content

def export_diagnostics(out_path):
    app_data = get_app_data_dir()
    config = load_config()
    
    secrets = []
    
    # Extract any obvious keys from config
    for k, v in config.items():
        if ("KEY" in k.upper() or "TOKEN" in k.upper()) and isinstance(v, str):
            secrets.append(v.strip())

    # And from environment
    api_key = os.environ.get("COURIER_API_KEY", "").strip()
    if api_key:
        secrets.append(api_key)
        
    token_file = app_data / "run" / "controller.token"
    if token_file.exists():
        token = token_file.read_text(encoding="utf-8").strip()
        if token:
            secrets.append(token)
            
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Export V1 ledger
        db_path = app_data / "courier.db"
        if db_path.exists():
            zf.write(db_path, "courier.db")
                
        # Export logs
        log_dir = app_data / "logs"
        if log_dir.exists():
            for f in log_dir.glob("*.log*"):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    if secrets:
                        text = redact_secrets(text, secrets)
                    zf.writestr(f"logs/{f.name}", text)
                except Exception:
                    pass
                    
        # Export config (redacted)
        config_path = app_data / "config.json"
        if config_path.exists():
            text = config_path.read_text(encoding="utf-8", errors="replace")
            if secrets:
                text = redact_secrets(text, secrets)
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
