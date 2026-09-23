#!/usr/bin/env python3
"""Publish only a schema-valid Codex RESULT for one validated courier TASK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path


EXPECTED = {
    "schema_version", "message_id", "task_id", "correlation_id", "parent_id",
    "source", "destination", "type", "status", "created_at", "payload",
    "payload_hash", "max_iterations",
}


def fail(message: str) -> None:
    raise SystemExit(f"invalid Codex courier result: {message}")


def payload_hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic_save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".tmp.{os.getpid()}.{int(time.time() * 1000)}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def publish_result(
    task_path: Path | str,
    processed_dir: Path | str,
    github_output: Path | str | None = None,
    raw_result: str | None = None,
) -> Path:
    t_path = Path(task_path)
    if not t_path.exists():
        fail(f"task file does not exist: {t_path}")
    try:
        task = json.loads(t_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"malformed task json: {exc}")

    result_str = raw_result if raw_result is not None else os.environ.get("CODEX_RESULT_JSON", "")
    try:
        result = json.loads(result_str)
    except json.JSONDecodeError as exc:
        fail(f"Codex output is not JSON: {exc.msg}")

    if set(result) != EXPECTED:
        fail("unexpected envelope fields")
    if result["schema_version"] != "2.0" or result["type"] != "RESULT" or result["status"] != "DONE":
        fail("unexpected result lifecycle")
    if result["source"] != "codex" or result["destination"] != "github_courier":
        fail("unexpected route")
    if result["task_id"] != task["task_id"] or result["correlation_id"] != task["correlation_id"]:
        fail("task or correlation mismatch")
    if result["parent_id"] != task["message_id"] or result["message_id"] == task["message_id"]:
        fail("parent or message identity mismatch")
    if result["max_iterations"] != task["max_iterations"] or result["max_iterations"] != 1:
        fail("iteration bound mismatch")
    expected_result = task.get("payload", {}).get("result_request")
    if expected_result not in {"COURIER_CODEX_ACK", "COURIER_SEQUENTIAL_ACK", "COURIER_AUTOMATIC_ACK"}:
        fail("unsupported task result_request")
    if result["payload"] != {"result": expected_result}:
        fail("unexpected payload")
    if result["payload_hash"] != payload_hash(result["payload"]):
        fail("payload hash mismatch")
    if not result["message_id"].replace("-", "").replace("_", "").replace(".", "").isalnum():
        fail("unsafe result message_id")

    p_dir = Path(processed_dir)
    p_dir.mkdir(parents=True, exist_ok=True)
    for candidate in p_dir.glob("*.json"):
        try:
            existing = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if existing.get("parent_id") == task["message_id"] or existing.get("message_id") == result["message_id"]:
            fail("duplicate terminal result")

    target = p_dir / f"{task['message_id']}.result.json"
    if target.exists():
        fail("terminal result path already exists")

    atomic_save_json(target, result)

    if github_output is not None:
        with Path(github_output).open("a", encoding="utf-8") as output:
            output.write(f"result_path={target.as_posix()}\n")

    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--processed-dir", required=True)
    parser.add_argument("--github-output", required=True)
    args = parser.parse_args()

    publish_result(args.task, args.processed_dir, github_output=args.github_output)


if __name__ == "__main__":
    main()
