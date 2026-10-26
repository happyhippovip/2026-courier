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

# Shapes that are secrets even when they are not in the local config.
TOKEN_SHAPES = re.compile(
    r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{8,}"
    r"|github_pat_[A-Za-z0-9_]{8,}"
    r"|sk-[A-Za-z0-9]{8,}"
    r"|xox[baprs]-[A-Za-z0-9-]{8,}"
    r"|Bearer\s+[A-Za-z0-9._\-]{8,}"
)


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
    home = get_app_data_dir()
    config_path = home / "config.json"
    if (home.is_symlink() or home.parent.is_symlink()
            or config_path.is_symlink() or config_path.parent.is_symlink()):
        return {}
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

def check_ledger():
    home = get_app_data_dir()
    db_path = home / "courier.db"
    if (home.is_symlink() or home.parent.is_symlink() or home.parent.parent.is_symlink()
            or db_path.is_symlink() or db_path.parent.is_symlink() or db_path.parent.parent.is_symlink()):
        return False, f"{db_path}: refusing to follow a symlink"
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
    return TOKEN_SHAPES.sub("***REDACTED***", content)


def _same_length_mask(value):
    """Keep the surrounding file the same size. A shorter mask corrupts SQLite."""
    return "*" * len(value)


def redact_secret_bytes(data, secrets):
    """Scrub a binary file without moving the bytes that follow a secret."""
    for secret in secrets:
        if secret and len(secret) > 4:
            raw = secret.encode("utf-8")
            data = data.replace(raw, b"*" * len(raw))
    text = data.decode("latin-1")
    text = TOKEN_SHAPES.sub(lambda match: _same_length_mask(match.group(0)), text)
    return text.encode("latin-1")

def export_diagnostics(out_path):
    app_data = get_app_data_dir()
    out = Path(out_path)
    token_file = app_data / "run" / "controller.token"
    db_path = app_data / "courier.db"
    log_dir = app_data / "logs"
    config_path = app_data / "config.json"
    if (app_data.is_symlink() or app_data.parent.is_symlink()
            or out.is_symlink() or out.parent.is_symlink()
            or token_file.is_symlink() or (app_data / "run").is_symlink()
            or db_path.is_symlink() or config_path.is_symlink() or log_dir.is_symlink()):
        raise OSError(f"{app_data}: refusing to follow a symlink")
    log_files = sorted(log_dir.glob("*.log*")) if log_dir.is_dir() else []
    if any(path.is_symlink() for path in log_files):
        raise OSError(f"{log_dir}: refusing to follow a symlink")
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
    if token_file.is_file():
        token = token_file.read_text(encoding="utf-8").strip()
        if token:
            secrets.append(token)
            
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Export V1 ledger
        db_path = app_data / "courier.db"
        if db_path.is_file() and not db_path.is_symlink():
            zf.writestr("courier.db", redact_secret_bytes(db_path.read_bytes(), secrets))
                
        # Export logs
        if log_files:
            for f in log_files:
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    if secrets:
                        text = redact_secrets(text, secrets)
                    zf.writestr(f"logs/{f.name}", text)
                except Exception:
                    pass
                    
        # Export config (redacted)
        config_path = app_data / "config.json"
        if config_path.is_file() and not config_path.is_symlink():
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
