#!/usr/bin/env python3
"""
Courier Doctor: Beginner UX tool to diagnose the health of the local Courier Symphony system.
"""

import json
import math
import os
import re
import sqlite3
import tempfile
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


# Same KEY/TOKEN rule as config collection, plus the password-like names that
# show up inside task params. Key walk is not enough: the same names also
# appear as "api_key=..." inside an otherwise harmless string.
_SENSITIVE_KEY_MARKERS = ("KEY", "TOKEN", "PASSWORD", "SECRET", "PASSWD", "CREDENTIAL")

# Assignment shapes follow scripts/resolve_project_memory.py SENSITIVE_PATTERNS.
# Token prefixes and high-entropy values cover secrets that have no label.
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|credential|oauth)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{5,})"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-._~+/]{5,}={0,2})")
_TOKEN_SHAPE_RE = re.compile(
    r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"AIza[0-9A-Za-z\-_]{35}|AKIA[0-9A-Z]{16}"
)
_ENTROPY_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9+/_\-]{20,}={0,2}(?![A-Za-z0-9])")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_REDACTION_NOTE = (
    "courier.db in a diagnostics bundle is a redacted copy of the local ledger.\n"
    "Secret-shaped values are replaced with ***REDACTED***. The live ledger is not modified.\n"
    "The copy will not verify against the journal hash chain, because payload bytes "
    "no longer match the stored hashes. That is expected.\n"
)


def _quote_ident(name):
    return '"' + name.replace('"', '""') + '"'


def _is_sensitive_key(name):
    upper = name.upper()
    return any(marker in upper for marker in _SENSITIVE_KEY_MARKERS)


def _remember_secret(secrets, value):
    if not isinstance(value, str):
        return
    for candidate in (value, value.strip()):
        if candidate and len(candidate) > 4 and candidate not in secrets:
            secrets.append(candidate)


def _walk_sensitive(value, found, sensitive):
    if isinstance(value, dict):
        for key, child in value.items():
            child_sensitive = sensitive or (isinstance(key, str) and _is_sensitive_key(key))
            _walk_sensitive(child, found, child_sensitive)
    elif isinstance(value, list):
        for child in value:
            _walk_sensitive(child, found, sensitive)
    elif sensitive and isinstance(value, str):
        found.append(value)


def _is_high_entropy(token):
    """Long mixed tokens only. Hex hashes and ids stay; they are not secrets."""
    if len(token) < 20 or _HEX_RE.match(token) or _UUID_RE.match(token):
        return False
    if not (re.search(r"[A-Z]", token) and re.search(r"[a-z]", token) and re.search(r"[0-9]", token)):
        return False
    counts = {}
    for ch in token:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(token)
    entropy = 0.0
    for count in counts.values():
        p = count / n
        entropy -= p * math.log2(p)
    return entropy >= 3.5


def _learn_value_secrets(text, secrets):
    """Learn secret strings from the text itself, whatever key they sit under."""
    if not isinstance(text, str) or not text:
        return
    for match in _ASSIGNMENT_RE.finditer(text):
        _remember_secret(secrets, match.group(2).rstrip(".,;:"))
    for match in _BEARER_RE.finditer(text):
        _remember_secret(secrets, match.group(1).rstrip(".,;:"))
    for match in _TOKEN_SHAPE_RE.finditer(text):
        _remember_secret(secrets, match.group(0))
    for match in _ENTROPY_RE.finditer(text):
        token = match.group(0)
        if _is_high_entropy(token):
            _remember_secret(secrets, token)


def _collect_text_secrets(text, secrets):
    _learn_value_secrets(text, secrets)
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return
    if not isinstance(parsed, (dict, list)):
        return
    found = []
    _walk_sensitive(parsed, found, False)
    for value in found:
        _remember_secret(secrets, value)
        if isinstance(value, str):
            _learn_value_secrets(value, secrets)


def _learn_text_file(path, secrets):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    _collect_text_secrets(text, secrets)


def _bundle_redaction_note(omission):
    note = _REDACTION_NOTE
    if omission:
        note += omission.rstrip() + "\n"
    return note


def _user_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def _table_columns(conn, table):
    rows = conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
    return [row[1] for row in rows]


def _open_readonly(db_path):
    return sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=5)


def _collect_db_secrets(db_path, secrets):
    """Pull secret strings out of ledger text.

    Task params are stored verbatim. Sensitive keys are one source. Values
    shaped like credentials are the other, so a secret under "note" is learned
    too. Config and the controller token never see those strings.
    """
    conn = _open_readonly(db_path)
    try:
        for table in _user_tables(conn):
            for column in _table_columns(conn, table):
                query = f"SELECT {_quote_ident(column)} FROM {_quote_ident(table)}"
                for (value,) in conn.execute(query):
                    if isinstance(value, str):
                        _collect_text_secrets(value, secrets)
    finally:
        conn.close()


def _redact_cell(value, secrets):
    if isinstance(value, str):
        return redact_secrets(value, secrets)
    if isinstance(value, bytes):
        redacted = value
        for secret in secrets:
            if secret and len(secret) > 4:
                redacted = redacted.replace(secret.encode("utf-8"), b"***REDACTED***")
        return redacted
    return value


def _schema_statements(conn):
    rows = conn.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
        ORDER BY CASE type
            WHEN 'table' THEN 0
            WHEN 'index' THEN 1
            WHEN 'trigger' THEN 2
            WHEN 'view' THEN 3
            ELSE 4
        END, name
        """
    ).fetchall()
    return [row[0] for row in rows]


def _write_redacted_database(src_path, dest_path, secrets):
    """Write a ledger copy whose pages never contained the secret strings.

    The live journal is append-only, and a page backup would keep freed
    pages. Inserting already-redacted cells into a new file is what a
    bytes-level scan of the zip member can actually hold.
    """
    src = _open_readonly(src_path)
    dest = sqlite3.connect(dest_path)
    try:
        version = src.execute("PRAGMA user_version").fetchone()[0]
        dest.execute("PRAGMA foreign_keys=OFF")
        for statement in _schema_statements(src):
            dest.execute(statement)
        dest.execute(f"PRAGMA user_version={int(version)}")
        for table in _user_tables(src):
            columns = _table_columns(src, table)
            if not columns:
                continue
            quoted = ", ".join(_quote_ident(column) for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            rows = src.execute(f"SELECT {quoted} FROM {_quote_ident(table)}").fetchall()
            redacted_rows = [
                tuple(_redact_cell(value, secrets) for value in row) for row in rows
            ]
            dest.executemany(
                f"INSERT INTO {_quote_ident(table)} ({quoted}) VALUES ({placeholders})",
                redacted_rows,
            )
        dest.commit()
    finally:
        src.close()
        dest.close()


def _finalize_secrets(secrets):
    # Longest first so a shorter secret cannot split a longer one.
    unique = []
    for secret in secrets:
        if secret and len(secret) > 4 and secret not in unique:
            unique.append(secret)
    unique.sort(key=len, reverse=True)
    return unique


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

    db_path = app_data / "courier.db"
    log_dir = app_data / "logs"
    config_path = app_data / "config.json"
    db_redactable = False
    harvest_failed = False
    if db_path.exists():
        try:
            _collect_db_secrets(db_path, secrets)
            db_redactable = True
        except sqlite3.Error:
            db_redactable = False
            harvest_failed = True

    # Inline secrets in logs and config have to join the list before any
    # member is written. Skip logs when the ledger could not be read: a raw
    # token copied out of it may not match a pattern, so those files stay out.
    if not harvest_failed and log_dir.exists():
        for log_file in log_dir.glob("*.log*"):
            _learn_text_file(log_file, secrets)
    if config_path.exists():
        _learn_text_file(config_path, secrets)
    secrets = _finalize_secrets(secrets)
            
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Export a redacted copy of the V1 ledger. Never the raw file:
        # task params are stored verbatim and may hold tokens.
        omission = None
        if db_path.exists() and db_redactable:
            try:
                with tempfile.TemporaryDirectory(prefix="courier-diag-") as tmp:
                    redacted_path = Path(tmp) / "courier.db"
                    _write_redacted_database(db_path, redacted_path, secrets)
                    zf.write(redacted_path, "courier.db")
            except sqlite3.Error:
                omission = (
                    "A redacted ledger copy could not be built, so courier.db "
                    "was omitted from this bundle."
                )
        elif db_path.exists():
            omission = (
                "The ledger could not be read, so courier.db was omitted from this bundle. "
                "Log files were also omitted so a secret that exists only in the unread "
                "ledger cannot leak through logs."
            )
        if db_path.exists():
            zf.writestr("courier.db.REDACTION.txt", _bundle_redaction_note(omission))
                
        # Export logs. Omitted entirely when ledger secret harvest failed.
        if log_dir.exists() and not harvest_failed:
            for f in log_dir.glob("*.log*"):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    if secrets:
                        text = redact_secrets(text, secrets)
                    zf.writestr(f"logs/{f.name}", text)
                except Exception:
                    pass
                    
        # Export config (redacted)
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
