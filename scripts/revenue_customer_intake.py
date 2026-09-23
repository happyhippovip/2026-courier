#!/usr/bin/env python3
import os
import sys
import json
import uuid
import re
import requests

DEFAULT_SERVER_URL = "http://127.0.0.1:8080"
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")
HEX_SHA_PATTERN = re.compile(r"^[a-fA-F0-9]{7,64}$")


def get_server_url() -> str:
    return os.environ.get("COURIER_SERVER", DEFAULT_SERVER_URL).rstrip("/")


def get_api_key() -> str:
    key = os.environ.get("COURIER_API_KEY")
    if key and key.strip():
        return key.strip()
    try:
        import keyring
        stored = keyring.get_password("courier", "api_key")
        if stored and stored.strip():
            return stored.strip()
    except Exception:
        pass
    return None


def get_headers(api_key: str = None) -> dict:
    key = api_key or get_api_key()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


# Module-level legacy aliases
API_URL = get_server_url()
API_KEY = get_api_key()
HEADERS = get_headers(API_KEY)


def validate_intake_inputs(owner: str, repo: str, sha: str, customer_ref: str) -> None:
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("owner must be a non-empty string")
    if not SAFE_IDENTIFIER_PATTERN.match(owner.strip()):
        raise ValueError(f"Invalid owner format: '{owner}' (must contain only alphanumeric characters, hyphens, underscores, or dots)")

    if not isinstance(repo, str) or not repo.strip():
        raise ValueError("repo must be a non-empty string")
    if not SAFE_IDENTIFIER_PATTERN.match(repo.strip()):
        raise ValueError(f"Invalid repo format: '{repo}' (must contain only alphanumeric characters, hyphens, underscores, or dots)")

    if not isinstance(sha, str) or not sha.strip():
        raise ValueError("sha must be a non-empty string")
    if not HEX_SHA_PATTERN.match(sha.strip()):
        raise ValueError(f"Invalid sha format: '{sha}' (must be a 7 to 64 character hex string)")

    if not isinstance(customer_ref, str) or not customer_ref.strip():
        raise ValueError("customer_ref must be a non-empty string")
    if any(ord(c) < 32 and c not in ("\t", "\n") for c in customer_ref):
        raise ValueError("customer_ref contains invalid control characters")


def submit_intake(
    owner: str,
    repo: str,
    sha: str,
    customer_ref: str,
    server_url: str = None,
    api_key: str = None,
    timeout: float = 10.0,
) -> dict:
    validate_intake_inputs(owner, repo, sha, customer_ref)

    effective_url = (server_url or get_server_url()).rstrip("/")
    effective_headers = get_headers(api_key)

    goal_id = f"REVENUE-GOAL-{uuid.uuid4().hex[:8].upper()}"
    task_id = f"REV-{uuid.uuid4().hex[:8].upper()}"

    goal_payload = {
        "goal_id": goal_id,
        "goal_text": f"Revenue Safety Audit for {owner.strip()}/{repo.strip()}",
        "workflow_plan": [
            {
                "task_id": task_id,
                "type": "revenue_safety_audit",
                "capabilities": ["revenue_safety_audit"],
                "target_owner": owner.strip(),
                "target_repo": repo.strip(),
                "target_sha": sha.strip(),
                "customer_reference": customer_ref.strip(),
                "dependencies": [],
                "status": "QUEUED",
                "target_agent": "linux",
                "idempotency_key": task_id,
            }
        ],
    }

    print(f"Submitting customer intake goal: {goal_id} for {owner}/{repo}")
    try:
        res = requests.post(
            f"{effective_url}/goals",
            json=goal_payload,
            headers=effective_headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        print(f"Failed to submit intake due to network exception: {exc}")
        return {
            "success": False,
            "error": f"Network error: {exc}",
            "status_code": None,
            "goal_id": goal_id,
            "task_id": task_id,
        }

    if 200 <= res.status_code < 300:
        print("Success!")
        res_data = {}
        try:
            res_data = res.json()
        except Exception:
            pass
        server_goal_id = res_data.get("goal_id", goal_id)
        return {
            "success": True,
            "goal_id": server_goal_id,
            "task_id": task_id,
            "status_code": res.status_code,
            "response": res_data,
        }
    else:
        print(f"Failed: {res.status_code} {res.text}")
        return {
            "success": False,
            "error": f"HTTP {res.status_code}: {res.text}",
            "status_code": res.status_code,
            "goal_id": goal_id,
            "task_id": task_id,
        }


def main():
    if len(sys.argv) < 5:
        print("Usage: python3 revenue_customer_intake.py <owner> <repo> <sha> <customer_ref>")
        sys.exit(1)

    api_key = get_api_key()
    if not api_key:
        print("FATAL: Missing COURIER_API_KEY, refusing to submit intake.")
        sys.exit(1)

    try:
        result = submit_intake(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], api_key=api_key)
        if not result.get("success"):
            sys.exit(1)
    except ValueError as exc:
        print(f"FATAL: Validation error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
