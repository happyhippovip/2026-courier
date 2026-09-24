#!/usr/bin/env python3
"""Courier Product Health Check.

Verifies end-to-end service health:
- Credential accessibility across environment variables, local .env files, and keyring
- Server connectivity and status endpoint
- Schema compatibility (goals and tasks keys)
- Active worker and verifier registration
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    import keyring
except ImportError:
    keyring = None


def get_api_key(repo_dir=None):
    """Retrieve API key from env, local .env files, or keyring (Windows Credential Manager)."""
    if repo_dir is None:
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # 1. Environment variable
    key = os.environ.get("COURIER_API_KEY")
    if key:
        return key

    # 2. Local environment files (.env.txt or .env)
    for env_name in [".env.txt", ".env"]:
        env_path = os.path.join(repo_dir, env_name)
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() in ("COURIER_API_KEY", "courier_api_key"):
                                return v.strip().strip('"\'')
            except Exception:
                pass

    # 3. Windows Credential Manager / Keyring
    if keyring:
        for service in ["courier_worker", "courier", "Courier"]:
            for key_name in ["courier_api_key", "COURIER_API_KEY"]:
                try:
                    val = keyring.get_password(service, key_name)
                    if val:
                        return val
                except Exception:
                    pass

    return None


def run(repo_dir=None, server_url=None):
    API_KEY = get_api_key(repo_dir)
    if not API_KEY:
        print("HUMAN_REQUIRED: No credentials found")
        return 1

    if server_url is None:
        server_url = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080")
    API_URL = server_url.rstrip("/")
    headers = {"Authorization": f"Bearer {API_KEY}"}

    try:
        req = urllib.request.Request(API_URL + "/status", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as f:
            status = json.loads(f.read().decode("utf-8"))
    except Exception as e:
        print("DEGRADED: Server unreachable or bad credentials: " + str(e))
        return 1

    if "goals" not in status or "tasks" not in status:
        print("DEGRADED: Schema incompatible (missing goals/tasks)")
        return 1

    try:
        req = urllib.request.Request(API_URL + "/workers", headers=headers)
        with urllib.request.urlopen(req, timeout=5) as f:
            workers = json.loads(f.read().decode("utf-8"))
    except Exception as e:
        print("DEGRADED: Workers endpoint failed: " + str(e))
        return 1

    now = time.time()
    verifier_found = False
    for w_id, w_data in workers.items():
        if "verifier" in w_id.lower():
            verifier_found = True
        hb = w_data.get("last_heartbeat", 0)
        if now - hb > 600:
            print("DEGRADED: Stale ownership / inactive worker " + w_id)
            return 1

    if not verifier_found:
        print("DEGRADED: No verifier registered or active")
        # Warn but do not fail dev check

    print("HEALTHY")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Courier Product Health Check")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--server", help="Server URL (default: COURIER_SERVER or http://127.0.0.1:8080)")
    args = parser.parse_args()

    exit_code = run(repo_dir=args.repo_dir, server_url=args.server)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
