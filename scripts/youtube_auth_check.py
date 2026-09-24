#!/usr/bin/env python3
"""YouTube API Read-Only Health Check.

Checks YouTube OAuth credentials and channel access without publishing anything.
Strictly read-only scope (https://www.googleapis.com/auth/youtube.readonly).
Supports --dry-run mode for offline/CI environments.
"""

import argparse
import json
import os
import sys
from pathlib import Path

READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


def check_youtube_auth(dry_run=False, token_path=None, client_secret_path=None, repo_dir=None):
    """Perform read-only YouTube health check.

    Returns a status dict. Never performs destructive or publishing actions.
    """
    if dry_run:
        return {
            "status": "DRY_RUN_OK",
            "mode": "dry-run",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "channel_id": "UC_dry_run_channel_001",
            "channel_title": "Courier Mock Channel (Dry Run)",
            "publish_allowed": False,
            "reason": "dry_run_mode_no_network"
        }

    # Resolve token/credentials locations safely
    if not token_path and repo_dir:
        cand_token = Path(repo_dir) / ".secrets/token.json"
        if cand_token.is_file():
            token_path = str(cand_token)
    if not client_secret_path and repo_dir:
        cand_secret = Path(repo_dir) / ".secrets/client_secret.json"
        if cand_secret.is_file():
            client_secret_path = str(cand_secret)

    token_file = (
        token_path
        or os.environ.get("YOUTUBE_OAUTH_TOKEN_PATH")
        or ".secrets/token.json"
    )
    secret_file = (
        client_secret_path
        or os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET_PATH")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ".secrets/client_secret.json"
    )

    token_exists = Path(token_file).is_file()
    secret_exists = Path(secret_file).is_file()

    # Fallback to keyring
    if not token_exists and not secret_exists:
        try:
            import keyring
            stored_token = keyring.get_password("courier", "YOUTUBE_OAUTH_TOKEN_PATH")
            if stored_token and Path(stored_token).is_file():
                token_file = stored_token
                token_exists = True
            stored_secret = keyring.get_password("courier", "YOUTUBE_OAUTH_CLIENT_SECRET_PATH")
            if stored_secret and Path(stored_secret).is_file():
                secret_file = stored_secret
                secret_exists = True
        except Exception:
            pass

    if not token_exists and not secret_exists:
        return {
            "status": "MISSING_CREDENTIALS",
            "mode": "live",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "channel_id": None,
            "channel_title": None,
            "publish_allowed": False,
            "reason": "Neither token.json nor client_secret.json found in environment, keyring, or .secrets/"
        }

    # If google client libraries are available and token exists, attempt read-only call
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if token_exists:
            creds = Credentials.from_authorized_user_file(token_file, [READONLY_SCOPE])
            service = build("youtube", "v3", credentials=creds)
            request = service.channels().list(mine=True, part="snippet,contentDetails")
            response = request.execute()
            items = response.get("items", [])
            if items:
                channel = items[0]
                return {
                    "status": "AUTHENTICATED",
                    "mode": "live",
                    "authenticated": True,
                    "read_only": True,
                    "scope": READONLY_SCOPE,
                    "channel_id": channel.get("id"),
                    "channel_title": channel.get("snippet", {}).get("title"),
                    "publish_allowed": False
                }
            return {
                "status": "NO_CHANNEL_FOUND",
                "mode": "live",
                "authenticated": True,
                "read_only": True,
                "scope": READONLY_SCOPE,
                "channel_id": None,
                "channel_title": None,
                "publish_allowed": False
            }
    except ImportError:
        return {
            "status": "DEPENDENCIES_MISSING",
            "mode": "live",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "channel_id": None,
            "channel_title": None,
            "publish_allowed": False,
            "reason": "google-api-python-client or google-auth not installed"
        }
    except Exception as exc:
        return {
            "status": "AUTH_ERROR",
            "mode": "live",
            "authenticated": False,
            "read_only": True,
            "scope": READONLY_SCOPE,
            "channel_id": None,
            "channel_title": None,
            "publish_allowed": False,
            "error": str(exc)
        }

    return {
        "status": "TOKEN_PENDING",
        "mode": "live",
        "authenticated": False,
        "read_only": True,
        "scope": READONLY_SCOPE,
        "channel_id": None,
        "channel_title": None,
        "publish_allowed": False,
        "reason": "client_secret present but token.json not yet generated via interactive OAuth"
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="YouTube API Health Check (Read-Only)")
    parser.add_argument("--dry-run", action="store_true", help="Run offline health check simulation")
    parser.add_argument("--token-path", default=None, help="Path to token.json")
    parser.add_argument("--client-secret-path", default=None, help="Path to client_secret.json")
    parser.add_argument("--repo-dir", default=None, help="Repository root path")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON only")
    args = parser.parse_args(argv)

    result = check_youtube_auth(
        dry_run=args.dry_run,
        token_path=args.token_path,
        client_secret_path=args.client_secret_path,
        repo_dir=args.repo_dir,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"YouTube Auth Status: {result['status']}")
        print(f"Mode: {result['mode']}")
        print(f"Scope: {result['scope']} (Read-Only)")
        if result.get("channel_title"):
            print(f"Channel: {result['channel_title']} ({result.get('channel_id')})")
        if result.get("reason"):
            print(f"Detail: {result['reason']}")

    # Exit code: 0 if DRY_RUN_OK or AUTHENTICATED, 1 otherwise
    if result["status"] in ("DRY_RUN_OK", "AUTHENTICATED"):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
