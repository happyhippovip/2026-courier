#!/usr/bin/env python3
"""Dispatch and reconcile one bounded Courier TaskPacket on GitHub Actions."""

from __future__ import annotations

import hashlib
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "happyhippovip/2026-courier")
WORKFLOW = "courier_worker.yml"
LOCAL_WAIT_SECONDS = int(os.environ.get("GITHUB_WORKER_LOCAL_WAIT_SECONDS", "60"))
POLL_SECONDS = 5
IDENTITY_FIELDS = (
    "goal_id",
    "task_id",
    "attempt_id",
    "dispatch_id",
    "execution_ref",
    "worker_id",
)
ALLOW_LIST = {"metadata", "report", "deterministic_transform", "verify_file", "static_analysis", "run_tests"}


def run_cmd(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, timeout=60, capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def state_path(task_file: Path) -> Path:
    return task_file.with_name(f"{task_file.stem}.github-worker-state.json")


def task_identity_sha256(task: dict[str, Any]) -> str:
    identity = {field: task[field] for field in IDENTITY_FIELDS}
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def task_packet_sha256(task: dict[str, Any]) -> str:
    encoded = json.dumps(task, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_state(task_file: Path, state: dict[str, Any]) -> None:
    state_path(task_file).write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")


def validate_task(task: dict[str, Any]) -> None:
    missing = [field for field in IDENTITY_FIELDS if not isinstance(task.get(field), str) or not task[field]]
    if missing:
        raise ValueError(f"TaskPacket is missing required identity fields: {', '.join(missing)}")
    if task.get("task_type", task.get("type")) not in ALLOW_LIST:
        raise ValueError("TaskPacket has an unsupported bounded task type")


def find_run(dispatch_id: str) -> tuple[str | None, str | None]:
    rc, output, error = run_cmd(["gh", "run", "list", "--repo", REPOSITORY, "--workflow", WORKFLOW, "--event",
                                 "workflow_dispatch", "--limit", "100", "--json", "databaseId,status,displayTitle"])
    if rc:
        raise RuntimeError(f"cannot list workflow runs: {error}")
    title = f"Courier dispatch {dispatch_id}"
    matches = [run for run in json.loads(output) if run.get("displayTitle") == title]
    if len(matches) > 1:
        raise RuntimeError(f"multiple GitHub runs found for dispatch_id {dispatch_id}")
    return (str(matches[0]["databaseId"]), matches[0]["status"]) if matches else (None, None)


def download_result(run_id: str, dispatch_id: str, destination: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    rc, _, error = run_cmd(["gh", "run", "download", run_id, "--repo", REPOSITORY, "--name",
                            f"courier-result-{dispatch_id}", "--dir", str(destination)])
    if rc:
        raise RuntimeError(f"cannot download dispatch artifact: {error}")
    result_files = list(destination.glob(f"result_{dispatch_id}.json"))
    evidence_files = list(destination.glob(f"courier_output_{dispatch_id}.json"))
    if len(result_files) != 1 or len(evidence_files) > 1:
        raise ValueError("dispatch artifact must contain exactly one result and at most one evidence file")
    evidence = json.loads(evidence_files[0].read_text(encoding="utf-8")) if evidence_files else None
    return json.loads(result_files[0].read_text(encoding="utf-8")), evidence


def verify_result(task: dict[str, Any], result: dict[str, Any], evidence: dict[str, Any] | None, run_id: str, directory: Path) -> None:
    if any(result.get(field) != task[field] for field in IDENTITY_FIELDS):
        raise ValueError("DurableResult identity does not match TaskPacket")
    if str(result.get("run_id")) != run_id or result.get("result_id") != f"result-{task['dispatch_id']}":
        raise ValueError("DurableResult is not bound to the observed GitHub run")
    if not isinstance(result.get("run_attempt"), str) or not result["run_attempt"].isdigit():
        raise ValueError("DurableResult is missing GitHub run_attempt")
    if result.get("status") == "FAILED":
        if result.get("artifacts") != [] or evidence is not None:
            raise ValueError("failed GitHub operation must not claim evidence")
        return
    if result.get("status") != "SUCCESS" or result.get("operation") != task.get("task_type", task.get("type")):
        raise ValueError("GitHub operation did not succeed")
    if evidence is None:
        raise ValueError("successful GitHub operation is missing evidence")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        raise ValueError("successful DurableResult requires one evidence artifact")
    artifact = artifacts[0]
    evidence_file = directory / artifact.get("path", "")
    if not evidence_file.is_file() or artifact.get("sha256") != hashlib.sha256(evidence_file.read_bytes()).hexdigest():
        raise ValueError("evidence artifact hash does not match")
    operation = result["operation"]
    if evidence.get("operation") != operation:
        raise ValueError("evidence operation mismatch")
    if operation == "deterministic_transform" and evidence.get("input_sha256") != hashlib.sha256(task["input"].encode()).hexdigest():
        raise ValueError("deterministic transform acceptance failed")
    if operation == "report" and evidence.get("report") != task.get("report"):
        raise ValueError("report acceptance failed")
    if operation == "verify_file" and evidence.get("path") != task.get("path"):
        raise ValueError("file verification acceptance failed")
    if operation in {"static_analysis", "run_tests"} and evidence.get("exit_code") != 0:
        raise ValueError("bounded verification acceptance failed")


def post_result(result: dict[str, Any]) -> None:
    key = os.environ.get("COURIER_API_KEY")
    if not key:
        raise RuntimeError("COURIER_API_KEY is required to post a DurableResult")
    url = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/") + "/tasks/result"
    response = requests.post(
        url,
        json=result,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Courier result POST failed: {response.status_code} {response.text}")


def run(task_file_name: str) -> int:
    task_file = Path(task_file_name)
    task = json.loads(task_file.read_text(encoding="utf-8"))
    validate_task(task)
    identity_sha256 = task_identity_sha256(task)
    packet_sha256 = task_packet_sha256(task)
    prior = {}
    if state_path(task_file).is_file():
        prior = json.loads(state_path(task_file).read_text(encoding="utf-8"))
        if prior.get("dispatch_id") != task["dispatch_id"]:
            raise ValueError("persisted GitHub state belongs to another dispatch")
        prior_identity = prior.get("task_identity_sha256")
        if prior_identity is not None and prior_identity != identity_sha256:
            raise ValueError("persisted GitHub state belongs to another task identity")
        prior_packet = prior.get("task_packet_sha256")
        if prior_packet is not None and prior_packet != packet_sha256:
            raise ValueError("persisted GitHub state belongs to another task packet")
        if prior.get("status") == "POSTED":
            if prior_identity is None or prior_packet is None:
                raise ValueError("posted GitHub state is missing bound task packet")
            return 0

    run_id, status = find_run(task["dispatch_id"])
    if not run_id and not prior:
        ref = os.environ.get("GITHUB_WORKER_REF") or run_cmd(["git", "branch", "--show-current"])[1]
        if not ref:
            raise RuntimeError("cannot determine dispatch ref")
        rc, _, error = run_cmd(["gh", "workflow", "run", WORKFLOW, "--repo", REPOSITORY, "--ref", ref,
                                "--raw-field", "task_payload_base64=" + base64.b64encode(
                                    json.dumps(task, separators=(",", ":")).encode("utf-8")).decode("ascii"),
                                "--field", f"dispatch_id={task['dispatch_id']}"])
        if rc:
            raise RuntimeError(f"workflow dispatch failed: {error}")
        write_state(task_file, {"dispatch_id": task["dispatch_id"], "task_identity_sha256": identity_sha256, "task_packet_sha256": packet_sha256, "status": "WAITING_FOR_WORKER"})

    deadline = time.monotonic() + LOCAL_WAIT_SECONDS
    while time.monotonic() < deadline:
        run_id, status = find_run(task["dispatch_id"])
        if run_id and status == "completed":
            directory = task_file.parent / f".courier-result-{task['dispatch_id']}"
            try:
                result, evidence = download_result(run_id, task["dispatch_id"], directory)
                verify_result(task, result, evidence, run_id, directory)
                post_result(result)
                write_state(task_file, {"dispatch_id": task["dispatch_id"], "task_identity_sha256": identity_sha256, "task_packet_sha256": packet_sha256, "run_id": run_id, "run_attempt": result["run_attempt"], "result_id": result["result_id"], "status": "POSTED"})
                return 0
            finally:
                shutil.rmtree(directory, ignore_errors=True)
        if run_id:
            write_state(task_file, {"dispatch_id": task["dispatch_id"], "task_identity_sha256": identity_sha256, "task_packet_sha256": packet_sha256, "run_id": run_id, "status": "WAITING_FOR_WORKER"})
        time.sleep(POLL_SECONDS)
    write_state(task_file, {"dispatch_id": task["dispatch_id"], "task_identity_sha256": identity_sha256, "task_packet_sha256": packet_sha256, "run_id": run_id, "status": "WAITING_FOR_WORKER"})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1]))
    except (IndexError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"GITHUB_WORKER_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
