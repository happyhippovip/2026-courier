#!/usr/bin/env python3
"""Deterministic, resilient customer intake dispatcher for Revenue V1."""

import json
import os
import re
import sys
import time
import uuid
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")
HEX_SHA_PATTERN = re.compile(r"^[a-fA-F0-9]{7,64}$")


def get_canonical_state_path(state_file: str = None) -> Path:
    if state_file:
        return Path(state_file).resolve()
    env_file = os.environ.get("COURIER_STATE_FILE")
    if env_file:
        return Path(env_file).resolve()
    default_server = REPO_ROOT / "server" / "state" / "central_state.json"
    if default_server.exists():
        return default_server
    root_candidate = REPO_ROOT / "central_state.json"
    if root_candidate.exists():
        return root_candidate
    return default_server


def atomic_save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f".tmp.{os.getpid()}.{int(time.time() * 1000)}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
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


def load_state_safe(path: Path) -> dict:
    if not path.exists():
        return {"tasks": {}, "workers": {}, "goals": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("State root must be a JSON dictionary")
            if "tasks" not in data:
                data["tasks"] = {}
            return data
    except (json.JSONDecodeError, ValueError, OSError):
        # Quarantine corrupt state to preserve forensics
        try:
            corrupt_path = path.with_name(f"{path.name}.corrupt.{int(time.time())}")
            os.replace(path, corrupt_path)
        except OSError:
            pass
        return {"tasks": {}, "workers": {}, "goals": {}}


def validate_intake_data(intake: dict) -> None:
    if not isinstance(intake, dict):
        raise ValueError("Intake content must be a JSON dictionary")

    owner = intake.get("target_owner")
    if not isinstance(owner, str) or not owner.strip() or not SAFE_IDENTIFIER_PATTERN.match(owner.strip()):
        raise ValueError(f"Invalid target_owner: '{owner}'")

    repo = intake.get("target_repo")
    if not isinstance(repo, str) or not repo.strip() or not SAFE_IDENTIFIER_PATTERN.match(repo.strip()):
        raise ValueError(f"Invalid target_repo: '{repo}'")

    sha = intake.get("target_sha")
    if not isinstance(sha, str) or not sha.strip() or not HEX_SHA_PATTERN.match(sha.strip()):
        raise ValueError(f"Invalid target_sha: '{sha}'")

    customer_ref = intake.get("customer_reference")
    if not isinstance(customer_ref, str) or not customer_ref.strip() or len(customer_ref) > 200:
        raise ValueError(f"Invalid customer_reference: '{customer_ref}'")
    if any(ord(c) < 32 for c in customer_ref):
        raise ValueError("customer_reference contains disallowed control characters")


def dispatch_intake(intake_file, state_file=None, gh_runner=None, wait_seconds=3) -> dict:
    intake_path = Path(intake_file)
    if not intake_path.exists():
        raise FileNotFoundError(f"Intake file does not exist: {intake_file}")

    with open(intake_path, "r", encoding="utf-8") as f:
        try:
            intake = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in intake file: {exc}")

    validate_intake_data(intake)

    task_id = f"task-revenue-{uuid.uuid4().hex[:8]}"
    print(f"Admitting intake {intake.get('customer_reference')} as {task_id}", flush=True)

    cmd = [
        "gh", "workflow", "run", "revenue_v1_baseline.yml",
        "-f", f"target_owner={intake['target_owner'].strip()}",
        "-f", f"target_repo={intake['target_repo'].strip()}",
        "-f", f"target_sha={intake['target_sha'].strip()}",
        "-f", f"customer_reference={intake['customer_reference'].strip()}",
        "-f", f"price_currency={intake.get('price_currency', 'EUR_99')}",
        "-f", f"delivery_destination={intake.get('delivery_destination', 'none')}"
    ]

    execution_ref = "DISPATCHED"
    if gh_runner is not None:
        execution_ref = gh_runner(cmd) or "DISPATCHED"
    else:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            print("Successfully dispatched to GitHub Actions worker.", flush=True)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            run_info = subprocess.run(
                ["gh", "run", "list", "--workflow=revenue_v1_baseline.yml", "--limit=1", "--json", "databaseId", "-q", ".[0].databaseId"],
                capture_output=True,
                text=True,
                timeout=30
            )
            out_ref = run_info.stdout.strip()
            if out_ref:
                execution_ref = out_ref
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            err_msg = getattr(e, "stderr", str(e))
            print(f"Failed to dispatch: {err_msg}", file=sys.stderr, flush=True)
            raise RuntimeError(f"GitHub workflow dispatch failed: {err_msg}")

    # Update Central State Atomically
    s_path = get_canonical_state_path(state_file)
    state = load_state_safe(s_path)

    state["tasks"][task_id] = {
        "task_id": task_id,
        "customer_reference": intake["customer_reference"].strip(),
        "worker_id": "github-actions-revenue-v1",
        "platform": "github",
        "dispatch_ref": "intake_dispatcher_local",
        "execution_ref": execution_ref,
        "state": "DISPATCHED_TO_EXTERNAL",
        "last_transition": "AUTOMATIC_DISPATCH",
        "next_explicit_transition": "WAIT_FOR_GITHUB_PR",
        "real_wall": "HUMAN_REVIEW_REQUIRED_ON_PR",
        "dispatched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    atomic_save_json(s_path, state)
    print("Central state updated. System chain fully connected for intake -> execution -> PR.", flush=True)

    return {
        "ok": True,
        "task_id": task_id,
        "customer_reference": intake["customer_reference"].strip(),
        "execution_ref": execution_ref,
        "state": "DISPATCHED_TO_EXTERNAL",
        "state_file": str(s_path),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/intake_dispatcher.py <intake_file.json>")
        sys.exit(1)
    try:
        dispatch_intake(sys.argv[1])
    except Exception as exc:
        print(f"INTAKE_ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
