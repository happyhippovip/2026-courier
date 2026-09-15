#!/usr/bin/env python3
"""Run Courier's fixed GitHub TaskPacket operation without interpreting payloads."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RUN_ID = re.compile(r"^[1-9][0-9]{0,19}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
SUPPORTED_OPERATION = "repository-metadata-v1"


def validate_taskpacket(packet: dict[str, object]) -> str | None:
    expected = {
        "schema_version", "task_id", "attempt_id", "dispatch_id", "result_id",
        "operation", "github_run_id", "github_run_attempt", "repository", "ref", "sha",
    }
    if set(packet) != expected:
        return "TaskPacket fields do not match the bounded schema"
    if packet["schema_version"] != "1.0":
        return "unsupported schema_version"
    for field in ("task_id", "attempt_id", "dispatch_id", "result_id"):
        if not isinstance(packet[field], str) or not IDENTITY.fullmatch(packet[field]):
            return f"invalid {field}"
    if packet["operation"] != SUPPORTED_OPERATION:
        return "unsupported operation"
    if not isinstance(packet["github_run_id"], str) or not RUN_ID.fullmatch(packet["github_run_id"]):
        return "invalid github_run_id"
    if not isinstance(packet["github_run_attempt"], int) or not 1 <= packet["github_run_attempt"] <= 100:
        return "invalid github_run_attempt"
    if not isinstance(packet["repository"], str) or not REPOSITORY.fullmatch(packet["repository"]):
        return "invalid repository"
    if not isinstance(packet["ref"], str) or not 1 <= len(packet["ref"]) <= 512:
        return "invalid ref"
    if not isinstance(packet["sha"], str) or not SHA.fullmatch(packet["sha"]):
        return "invalid sha"
    return None


def terminal_result(packet: dict[str, object], error: str | None) -> dict[str, object]:
    result = {
        "schema_version": "1.0",
        "task_id": packet["task_id"],
        "attempt_id": packet["attempt_id"],
        "dispatch_id": packet["dispatch_id"],
        "result_id": packet["result_id"],
        "operation": packet["operation"],
        "github_run_id": packet["github_run_id"],
        "github_run_attempt": packet["github_run_attempt"],
        "status": "REJECTED" if error else "SUCCEEDED",
        "terminal": True,
    }
    if error:
        result["error"] = error
    else:
        result["result"] = {
            "repository": packet["repository"],
            "ref": packet["ref"],
            "sha": packet["sha"],
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["execute"])
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    packet = {
        "schema_version": "1.0",
        "task_id": os.environ.get("TASK_ID", ""),
        "attempt_id": os.environ.get("ATTEMPT_ID", ""),
        "dispatch_id": os.environ.get("DISPATCH_ID", ""),
        "result_id": os.environ.get("RESULT_ID", ""),
        "operation": os.environ.get("OPERATION", ""),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "ref": os.environ.get("GITHUB_REF", ""),
        "sha": os.environ.get("GITHUB_SHA", ""),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "taskpacket.json").write_text(
        json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    result = terminal_result(packet, validate_taskpacket(packet))
    (args.output_dir / "result.json").write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
