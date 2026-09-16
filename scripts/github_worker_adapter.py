#!/usr/bin/env python3
"""Dispatch and reconcile one bounded Courier TaskPacket on GitHub Actions."""

from __future__ import annotations

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
POLL_SECONDS = 10
LOCAL_WAIT_SECONDS = int(os.environ.get("GITHUB_WORKER_LOCAL_WAIT_SECONDS", "60"))
TRANSIENT_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}
IDENTITY_FIELDS = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")


def run_cmd(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def state_path(task_file: Path) -> Path:
    return task_file.with_name(f"{task_file.stem}.github-worker-state.json")


def write_state(task_file: Path, state: dict[str, Any]) -> None:
    state_path(task_file).write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")


def validate_task(task: dict[str, Any]) -> None:
    missing = [field for field in IDENTITY_FIELDS if not isinstance(task.get(field), str) or not task[field]]
    if missing:
        raise ValueError(f"TaskPacket is missing required identity fields: {', '.join(missing)}")
    if task.get("task_type", task.get("type")) not in {
        "repo_inspect", "run_tests", "lint", "static_analysis", "package", "metadata",
        "report", "verify_file", "deterministic_transform",
    }:
        raise ValueError("TaskPacket has an unsupported bounded task type")


def find_run(dispatch_id: str) -> tuple[str | None, str | None]:
    rc, output, error = run_cmd(
        ["gh", "run", "list", "--workflow", WORKFLOW, "--event", "workflow_dispatch",
         "--limit", "100", "--json", "databaseId,status"]
    )
    if rc:
        raise RuntimeError(f"cannot list workflow runs: {error}")
    for candidate in json.loads(output):
        run_id = str(candidate["databaseId"])
        rc, artifacts, error = run_cmd(["gh", "api", f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts"])
        if rc:
            continue
        if any(artifact["name"] == f"courier-result-{dispatch_id}" for artifact in json.loads(artifacts)["artifacts"]):
            return run_id, candidate["status"]
    return None, None


def download_exact_result(run_id: str, dispatch_id: str, destination: Path) -> dict[str, Any] | None:
    artifact = f"courier-result-{dispatch_id}"
    rc, _, _ = run_cmd(["gh", "run", "download", run_id, "--name", artifact, "--dir", str(destination)])
    if rc:
        return None
    result_files = list(destination.glob(f"result_{dispatch_id}.json"))
    if len(result_files) != 1:
        return None
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    if result.get("dispatch_id") != dispatch_id or str(result.get("run_id")) != run_id:
        raise ValueError("downloaded result is not bound to the dispatched workflow run")
    return result



def post_result(result: dict[str, Any]) -> None:
    api_key = os.environ.get("COURIER_API_KEY")
    if not api_key:
        raise RuntimeError("COURIER_API_KEY is required to post a DurableResult")
    url = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/") + "/tasks/result"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    import random
    post_backoff = 2
    while True:
        try:
            response = requests.post(url, json=result, headers=headers, timeout=15)
            if response.status_code < 400:
                print(f"RESULT_POSTED_TO_COURIER=YES status={response.status_code}", flush=True)
                return
            if response.status_code not in TRANSIENT_HTTP_STATUSES:
                raise RuntimeError(f"result POST failed: {response.status_code} {response.text}")
        except requests.RequestException as exc:
            print(f"result POST failed: {exc}. Retrying in {post_backoff}s...")
        time.sleep(post_backoff + random.uniform(0, 2))
        post_backoff = min(60, post_backoff * 2)


def run(task_file_name: str) -> int:
    task_file = Path(task_file_name)
    task = json.loads(task_file.read_text(encoding="utf-8"))
    try:
        validate_task(task)
    except ValueError as exc:
        print(f"FAILED_TERMINAL={exc}", file=sys.stderr)
        # S08/S05 Fix: Post terminal failure back so server isn't stuck
        result = {
            "worker_id": task.get("worker_id", "GITHUB-HOSTED"),
            "goal_id": task.get("goal_id", ""),
            "task_id": task.get("task_id", ""),
            "attempt_id": task.get("attempt_id", ""),
            "dispatch_id": task.get("dispatch_id", ""),
            "run_id": "failed-early",
            "result_id": "failed-early",
            "status": "FAILED",
            "artifacts": [],
            "raw_result": {"status": "FAILED", "reason": "VALIDATION_ERROR", "stderr": str(exc)}
        }
        try:
            post_result(result)
        except Exception:
            pass
        return 2

    prior = {}
    if state_path(task_file).exists():
        prior = json.loads(state_path(task_file).read_text(encoding="utf-8"))
    run_id = prior.get("run_id")
    status = prior.get("status")
    if not run_id:
        ref = os.environ.get("GITHUB_WORKER_REF")
        if not ref:
            rc, ref, error = run_cmd(["git", "branch", "--show-current"])
            if rc or not ref:
                raise RuntimeError(f"cannot determine dispatch ref: {error}")
        rc, _, error = run_cmd(["gh", "workflow", "run", WORKFLOW, "--ref", ref,
                                "--field", f"task_payload={json.dumps(task, separators=(',', ':'))}"])
        if rc:
            raise RuntimeError(f"workflow dispatch failed: {error}")
        write_state(task_file, {"dispatch_id": task["dispatch_id"], "status": "WAITING_FOR_WORKER"})

    deadline = time.monotonic() + LOCAL_WAIT_SECONDS
    while time.monotonic() < deadline:
        run_id, status = find_run(task["dispatch_id"])
        if run_id and status == "completed":
            download_dir = task_file.parent / f".courier-result-{task['dispatch_id']}"
            try:
                result = download_exact_result(run_id, task["dispatch_id"], download_dir)
                if result is None:
                    raise RuntimeError("completed matching run did not publish an exact durable result artifact")
                if any(result.get(field) != task[field] for field in IDENTITY_FIELDS):
                    raise ValueError("durable result identity does not match TaskPacket")
                for art in result.get("artifacts", []):
                    art_path = download_dir / art.get("path", "")
                    if art_path.exists():
                        shutil.copy(art_path, ".")
                post_result(result)
                write_state(task_file, {"dispatch_id": task["dispatch_id"], "run_id": run_id, "status": "POSTED",
                                        "result_id": result["result_id"]})
                print(f"GITHUB_RUN_ID={run_id}\nRESULT_ID={result['result_id']}", flush=True)
                return 0
            finally:
                shutil.rmtree(download_dir, ignore_errors=True)
        if run_id:
            write_state(task_file, {"dispatch_id": task["dispatch_id"], "run_id": run_id, "status": status})
        time.sleep(POLL_SECONDS)

    write_state(task_file, {"dispatch_id": task["dispatch_id"], "run_id": run_id, "status": "WAITING_FOR_WORKER"})
    print(f"WAITING_FOR_WORKER dispatch_id={task['dispatch_id']} run_id={run_id or 'pending'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1]))
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"GITHUB_WORKER_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
