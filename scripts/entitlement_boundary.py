#!/usr/bin/env python3
"""Commercial tier entitlements and capability boundaries for Courier."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent

DEFAULT_ENTITLEMENT = {
    "tier": "COMMUNITY",
    "max_concurrent_tasks": 2,
    "features": ["local_execution", "basic_reporting"],
}


def resolve_license_path(license_path: str | Path | None = None) -> Path:
    if license_path:
        p = Path(license_path)
        if not p.is_absolute():
            p = (REPO_DIR / p).resolve() if (REPO_DIR / p).exists() else p.resolve()
        return p
    env_path = os.environ.get("COURIER_LICENSE_PATH")
    if env_path:
        return Path(env_path).resolve()
    return REPO_DIR / "license.json"


def load_entitlements(license_path: str | Path | None = None) -> dict:
    """Loads commercial tier limits and capabilities.

    Fails open to a FREE/COMMUNITY tier if missing or invalid.
    """
    resolved = resolve_license_path(license_path)
    if resolved.exists() and resolved.is_file():
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data.get("entitlements", DEFAULT_ENTITLEMENT)
        except Exception:
            pass

    return dict(DEFAULT_ENTITLEMENT)


def check_capability(capability_name: str, license_path: str | Path | None = None) -> bool:
    entitlements = load_entitlements(license_path)
    return capability_name in entitlements.get("features", [])


def get_task_limit(license_path: str | Path | None = None) -> int:
    entitlements = load_entitlements(license_path)
    return int(entitlements.get("max_concurrent_tasks", DEFAULT_ENTITLEMENT["max_concurrent_tasks"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check commercial tier entitlements")
    parser.add_argument("--license", help="Path to license.json")
    parser.add_argument("--check", help="Check if a specific capability/feature is entitled")
    parser.add_argument("--limit", action="store_true", help="Print task concurrency limit only")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    if args.check:
        allowed = check_capability(args.check, license_path=args.license)
        if args.json:
            print(json.dumps({"capability": args.check, "allowed": allowed}))
        else:
            print(f"Capability '{args.check}': {'ALLOWED' if allowed else 'DENIED'}")
        return 0 if allowed else 1

    if args.limit:
        limit = get_task_limit(license_path=args.license)
        if args.json:
            print(json.dumps({"max_concurrent_tasks": limit}))
        else:
            print(limit)
        return 0

    ents = load_entitlements(license_path=args.license)
    if args.json:
        print(json.dumps(ents, indent=2))
    else:
        print(f"Current Tier: {ents['tier']}")
        print(f"Max Concurrent Tasks: {ents['max_concurrent_tasks']}")
        print(f"Features: {ents['features']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
