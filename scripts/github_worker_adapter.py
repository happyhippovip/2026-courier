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
import threading
import time
from pathlib import Path
from typing import Any

import requests

REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "happyhippovip/2026-courier")
WORKFLOW = "courier_worker.yml"
LOCAL_WAIT_SECONDS = int(os.environ.get("GITHUB_WORKER_LOCAL_WAIT_SECONDS", "60"))
POLL_SECONDS = 5
# How long a resumed adapter waits for a run from an interrupted dispatch to
# appear before dispatching exactly once more. Covers GitHub list latency so
# a crash between `gh workflow run` and the WAITING record cannot create a
# second external run (which would wedge find_run on multiple title matches).
DISPATCH_GRACE_SECONDS = int(os.environ.get("GITHUB_WORKER_DISPATCH_GRACE_SECONDS", "300"))
# A packet must never be worked by two adapters at once (duplicate external
# dispatch + duplicate POST). The lock is per packet, held only for one run()
# call; a crashed holder's lock goes stale and is stolen, so work is delayed
# but never lost and never duplicated.
LOCK_TIMEOUT_SECONDS = int(os.environ.get("GITHUB_WORKER_LOCK_TIMEOUT_SECONDS", "600"))


def lock_path(task_file: Path) -> Path:
    # Leading dot: dispatcher resume globs `dispatch-*.json`, which never
    # matches dotfiles, so a lock is never mistaken for a packet.
    return task_file.with_name(f".{task_file.stem}.lock")


def _write_lock_tmp(task_file: Path) -> Path:
    """Stage this worker's lock claim in a thread-unique tmp file.

    The claim is published with os.link(), which is atomic and exclusive:
    readers of the lock path only ever see complete content or nothing, so
    a racing reader can never observe a torn claim.
    """
    tmp = task_file.with_name(f".{task_file.stem}.{os.getpid()}.{threading.get_ident()}.locktmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "started_at": time.time()}, f)
        f.flush()
        os.fsync(f.fileno())
    return tmp


def acquire_packet_lock(task_file: Path) -> bool:
    """Take the per-packet lock. True when this worker owns the packet."""
    path = lock_path(task_file)
    tmp = _write_lock_tmp(task_file)
    try:
        os.link(tmp, path)
    except FileExistsError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return _steal_stale_lock(task_file, path)
    try:
        os.unlink(tmp)
    except OSError:
        pass
    return True


def _steal_stale_lock(task_file: Path, path: Path) -> bool:
    # Lock content is published atomically (link of a complete tmp), so a
    # present lock always parses; unparseable means a foreign writer — treat
    # as live and defer rather than risk duplicating its work.
    try:
        started_at = float(json.loads(path.read_text(encoding="utf-8")).get("started_at") or 0)
    except (OSError, ValueError, TypeError, AttributeError):
        return False
    if time.time() - started_at < LOCK_TIMEOUT_SECONDS:
        return False  # live holder owns the packet; defer to it
    try:
        os.unlink(path)
    except OSError:
        return False
    tmp = _write_lock_tmp(task_file)
    try:
        os.link(tmp, path)
    except FileExistsError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return False  # another worker stole it first
    try:
        os.unlink(tmp)
    except OSError:
        pass
    return True


def release_packet_lock(task_file: Path) -> None:
    try:
        os.unlink(lock_path(task_file))
    except OSError:
        pass
IDENTITY_FIELDS = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")
ALLOW_LIST = {"metadata", "report", "deterministic_transform", "verify_file", "static_analysis", "run_tests"}


def run_cmd(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def state_path(task_file: Path) -> Path:
    return task_file.with_name(f"{task_file.stem}.github-worker-state.json")


def write_state(task_file: Path, state: dict[str, Any]) -> None:
    # Atomic publish: a kill between truncate and content commit must never
    # leave a torn state file behind (torn state crashes every future run
    # with JSONDecodeError while resume keeps respawning into the crash).
    # The tmp name is thread-unique and has no .json suffix, so neither the
    # resume glob nor the lock logic can mistake it for a packet or a lock.
    tmp = task_file.with_name(f".{task_file.stem}.{os.getpid()}.{threading.get_ident()}.statetmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(state, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, state_path(task_file))


def validate_task(task: dict[str, Any]) -> None:
    missing = [field for field in IDENTITY_FIELDS if not isinstance(task.get(field), str) or not task[field]]
    if missing:
        raise ValueError(f"TaskPacket is missing required identity fields: {', '.join(missing)}")
    if task.get("task_type", task.get("type")) not in ALLOW_LIST:
        raise ValueError("TaskPacket has an unsupported bounded task type")
    if task.get("task_type", task.get("type")) == "deterministic_transform" and not isinstance(task.get("input"), str):
        raise ValueError("TaskPacket deterministic_transform requires a string input")


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
    if not isinstance(result, dict):
        raise ValueError("DurableResult must be a JSON object")
    if evidence is not None and not isinstance(evidence, dict):
        raise ValueError("evidence must be a JSON object or null")
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
    evidence_path = artifact.get("path", "")
    if not isinstance(evidence_path, str) or not evidence_path or Path(evidence_path).is_absolute() or ".." in Path(evidence_path).parts:
        raise ValueError("evidence artifact path escapes the download directory")
    evidence_file = directory / evidence_path
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


def dispatch_external(task_file: Path, task: dict[str, Any]) -> None:
    """Dispatch exactly one external run, bracketed by durable state.

    The DISPATCHING marker goes down first so a crash around the `gh` call
    is distinguishable from a fresh admission on resume; the WAITING record
    confirms the dispatch completed.
    """
    ref = os.environ.get("GITHUB_WORKER_REF") or run_cmd(["git", "branch", "--show-current"])[1]
    if not ref:
        raise RuntimeError("cannot determine dispatch ref")
    write_state(task_file, {"dispatch_id": task["dispatch_id"], "status": "DISPATCHING",
                            "dispatched_at": time.time()})
    rc, _, error = run_cmd(["gh", "workflow", "run", WORKFLOW, "--repo", REPOSITORY, "--ref", ref,
                            "--raw-field", "task_payload_base64=" + base64.b64encode(
                                json.dumps(task, separators=(",", ":")).encode("utf-8")).decode("ascii"),
                            "--field", f"dispatch_id={task['dispatch_id']}"])
    if rc:
        raise RuntimeError(f"workflow dispatch failed: {error}")
    write_state(task_file, {"dispatch_id": task["dispatch_id"], "status": "WAITING_FOR_WORKER"})


def await_dispatched_run(task: dict[str, Any], prior: dict[str, Any]) -> bool:
    """Wait up to the marker's grace for the interrupted dispatch's run.

    Returns True when a run for this dispatch_id becomes visible (the caller
    adopts it instead of dispatching again).
    """
    try:
        deadline = float(prior.get("dispatched_at") or 0) + DISPATCH_GRACE_SECONDS
    except (TypeError, ValueError):
        return False
    while time.time() < deadline:
        time.sleep(POLL_SECONDS)
        run_id, _ = find_run(task["dispatch_id"])
        if run_id:
            return True
    run_id, _ = find_run(task["dispatch_id"])
    return bool(run_id)


def run(task_file_name: str) -> int:
    task_file = Path(task_file_name)
    task = json.loads(task_file.read_text(encoding="utf-8"))
    if not acquire_packet_lock(task_file):
        print(f"Packet {task.get('dispatch_id')} is already being processed; deferring.")
        return 0
    try:
        return _run(task_file, task)
    finally:
        release_packet_lock(task_file)


def _run(task_file: Path, task: dict[str, Any]) -> int:
    validate_task(task)
    prior = {}
    if state_path(task_file).is_file():
        prior = json.loads(state_path(task_file).read_text(encoding="utf-8"))
        if prior.get("dispatch_id") != task["dispatch_id"]:
            raise ValueError("persisted GitHub state belongs to another dispatch")
        if prior.get("status") == "POSTED":
            return 0

    run_id, status = find_run(task["dispatch_id"])
    if not run_id and not prior:
        dispatch_external(task_file, task)
    elif not run_id and prior.get("status") == "DISPATCHING":
        # An earlier attempt recorded its intent but never confirmed WAITING:
        # either it crashed around the external dispatch or GitHub has not
        # listed the new run yet. Adopt the run if it appears within grace;
        # dispatch exactly once more only when the marker is stale and no
        # run exists, so a crash can neither duplicate nor lose the dispatch.
        if not await_dispatched_run(task, prior):
            dispatch_external(task_file, task)

    deadline = time.monotonic() + LOCAL_WAIT_SECONDS
    while time.monotonic() < deadline:
        run_id, status = find_run(task["dispatch_id"])
        if run_id and status == "completed":
            directory = task_file.parent / f".courier-result-{task['dispatch_id']}"
            try:
                result, evidence = download_result(run_id, task["dispatch_id"], directory)
                verify_result(task, result, evidence, run_id, directory)
                post_result(result)
                write_state(task_file, {"dispatch_id": task["dispatch_id"], "run_id": run_id, "run_attempt": result["run_attempt"], "result_id": result["result_id"], "status": "POSTED"})
                return 0
            finally:
                shutil.rmtree(directory, ignore_errors=True)
        if run_id:
            write_state(task_file, {"dispatch_id": task["dispatch_id"], "run_id": run_id, "status": "WAITING_FOR_WORKER"})
        time.sleep(POLL_SECONDS)
    write_state(task_file, {"dispatch_id": task["dispatch_id"], "run_id": run_id, "status": "WAITING_FOR_WORKER"})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1]))
    except (IndexError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"GITHUB_WORKER_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
