#!/usr/bin/env python3
"""Independently verify a terminal result against the dispatched Courier identities."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from scripts.run_github_taskpacket import IDENTITY, RUN_ID
except ModuleNotFoundError:
    from run_github_taskpacket import IDENTITY, RUN_ID


VERIFIER_ID = "github-actions-taskpacket-verifier-v1"


def fail(message: str) -> None:
    raise SystemExit(f"invalid TaskPacket terminal result: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    expected_identities = {
        "task_id": os.environ["TASK_ID"],
        "attempt_id": os.environ["ATTEMPT_ID"],
        "dispatch_id": os.environ["DISPATCH_ID"],
        "result_id": os.environ["RESULT_ID"],
        "github_run_id": os.environ["GITHUB_RUN_ID"],
        "github_run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
    }
    if result.get("schema_version") != "1.0" or result.get("terminal") is not True:
        fail("not a supported terminal result")
    if result.get("status") not in {"SUCCEEDED", "REJECTED"}:
        fail("invalid status")
    for field, expected in expected_identities.items():
        if result.get(field) != expected:
            fail(f"{field} does not match this dispatch")
    for field in ("task_id", "attempt_id", "dispatch_id", "result_id"):
        if not IDENTITY.fullmatch(result[field]):
            fail(f"invalid {field}")
    if not RUN_ID.fullmatch(result["github_run_id"]):
        fail("invalid github_run_id")
    if result["status"] == "SUCCEEDED":
        if set(result) != {
            "schema_version", "task_id", "attempt_id", "dispatch_id", "result_id",
            "operation", "github_run_id", "github_run_attempt", "status", "terminal", "result",
        }:
            fail("unexpected succeeded result fields")
    elif set(result) != {
        "schema_version", "task_id", "attempt_id", "dispatch_id", "result_id",
        "operation", "github_run_id", "github_run_attempt", "status", "terminal", "error",
    }:
        fail("unexpected rejected result fields")

    verification = {
        "schema_version": "1.0",
        "verifier_id": VERIFIER_ID,
        "verified": True,
        "result_path": "result.json",
        **expected_identities,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verification, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(json.dumps(verification, sort_keys=True))


if __name__ == "__main__":
    main()
