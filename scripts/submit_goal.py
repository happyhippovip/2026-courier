#!/usr/bin/env python3
"""Submit Goal to Courier Central Server.

Validates and submits a canonical GOAL payload to the Courier REST API.
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
import requests

API_URL = os.environ.get('COURIER_SERVER', 'http://127.0.0.1:8080').rstrip('/')


def get_api_key() -> str | None:
    if os.environ.get("COURIER_API_KEY"):
        return os.environ["COURIER_API_KEY"]
    try:
        import keyring
        for service, user in [
            ("courier_worker", "courier_api_key"),
            ("courier_worker", "COURIER_API_KEY"),
            ("courier", "COURIER_API_KEY"),
            ("courier", "api_key"),
        ]:
            key = keyring.get_password(service, user)
            if key:
                return key
    except Exception:
        pass
    return None


def submit_goal(
    goal_text: str | None = None,
    json_file: str | None = None,
    api_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 10.0,
) -> dict:
    url = (api_url or API_URL).rstrip('/')
    resolved_key = api_key or get_api_key()
    headers = {
        'Authorization': f'Bearer {resolved_key}',
        'Content-Type': 'application/json'
    }

    goal_id = f"GOAL-{uuid.uuid4().hex[:8].upper()}"

    if json_file:
        with open(json_file, 'r', encoding="utf-8") as f:
            goal_payload = json.load(f)
        if 'goal_id' not in goal_payload:
            goal_payload['goal_id'] = goal_id
        else:
            goal_id = goal_payload['goal_id']
    else:
        goal_payload = {
            'goal_id': goal_id,
            'goal_text': goal_text
        }

    try:
        res = requests.post(f"{url}/goals", json=goal_payload, headers=headers, timeout=timeout)
        if res.status_code == 200:
            return {
                "status": "SUCCESS",
                "goal_id": goal_id,
                "status_code": 200,
                "response": res.json() if res.headers.get("content-type") == "application/json" else res.text
            }
        else:
            return {
                "status": "FAILED",
                "goal_id": goal_id,
                "status_code": res.status_code,
                "error": res.text
            }
    except Exception as e:
        return {
            "status": "ERROR",
            "goal_id": goal_id,
            "error": str(e)
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a goal to Courier")
    parser.add_argument('--file', help="Path to JSON file containing full goal payload (including workflow_plan)")
    parser.add_argument('--server', help="Courier server URL")
    parser.add_argument('--api-key', help="API authorization key")
    parser.add_argument('--json', action="store_true", help="Output machine-readable JSON status")
    parser.add_argument('goal_text', nargs='?', help="Goal text to formulate plan for")

    args = parser.parse_args(argv)

    if not args.file and not args.goal_text:
        parser.print_help()
        return 1

    result = submit_goal(
        goal_text=args.goal_text,
        json_file=args.file,
        api_url=args.server,
        api_key=args.api_key,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "SUCCESS":
            print(f"Successfully submitted to Courier Central Server: {result['goal_id']}")
        else:
            print(f"Goal submission {result['status']}: {result.get('error', 'unknown error')}")

    return 0 if result["status"] == "SUCCESS" else 1


if __name__ == '__main__':
    sys.exit(main())
