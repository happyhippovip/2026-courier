#!/usr/bin/env python3
"""TikTok API Read-Only Health Check.

Checks TikTok API credentials and account access without publishing anything.
Strictly read-only scope (user.info.basic).
Supports --dry-run mode for offline/CI environments.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

READONLY_SCOPE = "user.info.basic"
TIKTOK_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/?fields=open_id,union_id,avatar_url,display_name"


def check_tiktok_auth(dry_run=False, token=None, token_path=None):
    """Perform read-only TikTok health check.

    Returns a status dict. Never performs destructive or publishing actions.
    """
    if dry_run:
        return {
            "status": "DRY_RUN_OK",
            "mode": "dry-run",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "open_id": "mock_tiktok_open_id_001",
            "display_name": "Courier Mock Creator (Dry Run)",
            "publish_allowed": False,
            "reason": "dry_run_mode_no_network"
        }

    # Resolve token safely from param, env, or secrets file
    resolved_token = token or os.environ.get("TIKTOK_ACCESS_TOKEN")
    token_file = token_path or os.environ.get("TIKTOK_TOKEN_PATH") or ".secrets/tiktok_token.json"

    if not resolved_token and Path(token_file).is_file():
        try:
            data = json.loads(Path(token_file).read_text(encoding="utf-8"))
            resolved_token = data.get("access_token") or data.get("token")
        except Exception:
            resolved_token = None

    if not resolved_token:
        return {
            "status": "MISSING_CREDENTIALS",
            "mode": "live",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "open_id": None,
            "display_name": None,
            "publish_allowed": False,
            "reason": "No TikTok access token found in environment or .secrets/tiktok_token.json"
        }

    # Execute read-only request using stdlib urllib
    try:
        req = urllib.request.Request(TIKTOK_USER_INFO_URL, method="GET")
        req.add_header("Authorization", f"Bearer {resolved_token}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            data = body.get("data", {}).get("user", {})
            error_info = body.get("error", {})
            if error_info.get("code") and error_info.get("code") != "ok":
                return {
                    "status": "AUTH_ERROR",
                    "mode": "live",
                    "authenticated": False,
                    "read_only": True,
                    "scope": READONLY_SCOPE,
                    "open_id": None,
                    "display_name": None,
                    "publish_allowed": False,
                    "error": error_info.get("message", "Unknown TikTok API error")
                }
            return {
                "status": "AUTHENTICATED",
                "mode": "live",
                "authenticated": True,
                "read_only": True,
                "scope": READONLY_SCOPE,
                "open_id": data.get("open_id"),
                "display_name": data.get("display_name"),
                "publish_allowed": False
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": "AUTH_ERROR",
            "mode": "live",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "open_id": None,
            "display_name": None,
            "publish_allowed": False,
            "error": f"HTTP {exc.code}: {exc.reason}"
        }
    except Exception as exc:
        return {
            "status": "AUTH_ERROR",
            "mode": "live",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "open_id": None,
            "display_name": None,
            "publish_allowed": False,
            "error": str(exc)
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description="TikTok API Health Check (Read-Only)")
    parser.add_argument("--dry-run", action="store_true", help="Run offline health check simulation")
    parser.add_argument("--token", default=None, help="TikTok access token")
    parser.add_argument("--token-path", default=None, help="Path to tiktok_token.json")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON only")
    args = parser.parse_args(argv)

    result = check_tiktok_auth(
        dry_run=args.dry_run,
        token=args.token,
        token_path=args.token_path,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"TikTok Auth Status: {result['status']}")
        print(f"Mode: {result['mode']}")
        print(f"Scope: {result['scope']} (Read-Only)")
        if result.get("display_name"):
            print(f"User: {result['display_name']} ({result.get('open_id')})")
        if result.get("reason"):
            print(f"Detail: {result['reason']}")
        if result.get("error"):
            print(f"Error: {result['error']}")

    if result["status"] in ("DRY_RUN_OK", "AUTHENTICATED"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
