#!/usr/bin/env python3
"""
Courier Doctor: Beginner UX tool to diagnose the health of the local Courier Symphony system.
"""

import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
import time
import zipfile

# Env/config names that plausibly carry credentials. Mirrors the config-key
# heuristic below so a credential moved from config to environment (or vice
# versa) stays redacted in diagnostics bundles either way.
SECRET_NAME_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.IGNORECASE)

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

def check_server():
    config = load_config()
    server = os.environ.get("COURIER_SERVER") or os.environ.get("COURIER_SERVER_URL") or config.get("COURIER_SERVER") or "http://127.0.0.1:8080"
    if server.lower() == "local":
        server = "http://127.0.0.1:8080"
    server = server.rstrip("/")
    try:
        req = urllib.request.Request(f"{server}/v1/health")
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

    # And from the environment: every credential-looking variable, not just
    # COURIER_API_KEY, so verifier/provider keys set via env cannot leak
    # into the bundled logs and config copies.
    for name, value in os.environ.items():
        if SECRET_NAME_RE.search(name) and isinstance(value, str) and value.strip():
            secrets.append(value.strip())

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
