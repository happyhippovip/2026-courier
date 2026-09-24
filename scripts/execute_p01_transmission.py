#!/usr/bin/env python3
"""Execute P-01 Transmission.

Executes transmission of the P-01 follow-up specification, updating the spec atomically.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def transmit_p01(
    repo_dir: str | Path | None = None,
    spec_path: str | Path | None = None,
    quiet: bool = False,
) -> dict | None:
    if repo_dir is None:
        repo_dir = Path(__file__).resolve().parent.parent
    else:
        repo_dir = Path(repo_dir).resolve()

    target_path = Path(spec_path) if spec_path else repo_dir / "events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json"
    if not target_path.exists():
        if not quiet:
            print(f"Spec file not found: {target_path}")
        return None

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as e:
        if not quiet:
            print(f"Failed to read spec file: {e}")
        return None

    current_status = spec.get("current_status")
    if current_status == "WAITING_FOR_HUMAN":
        if not quiet:
            print("CHIEF OVERRIDE: Executing P-01 Transmission...")
        spec["current_status"] = "TRANSMITTED_BY_CHIEF"
        spec["transmitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_file = tempfile.mkstemp(dir=target_path.parent, prefix="p01_", suffix=".tmp")
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)
        os.replace(tmp_file, target_path)

        if not quiet:
            print(f"Success: P-01 Follow-Up Transmitted at {spec['transmitted_at']}")
            print(f"Fingerprint: {spec.get('message_fingerprint')}")
        return spec
    else:
        if not quiet:
            print(f"P-01 already in status: {current_status}")
        return spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute P-01 Follow-Up Transmission")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--spec-path", help="Path to custom spec JSON file")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON status")
    args = parser.parse_args(argv)

    spec = transmit_p01(repo_dir=args.repo_dir, spec_path=args.spec_path, quiet=args.json)
    if spec is None:
        if args.json:
            print(json.dumps({"status": "FAILED", "reason": "SPEC_NOT_FOUND"}))
        return 1

    if args.json:
        print(json.dumps({
            "status": "SUCCESS",
            "current_status": spec.get("current_status"),
            "transmitted_at": spec.get("transmitted_at"),
            "message_fingerprint": spec.get("message_fingerprint")
        }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
