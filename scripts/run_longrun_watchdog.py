#!/usr/bin/env python3
"""Bounded, idle-aware wrapper for Courier's autonomous supervisor."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_autonomous_supervisor import AutonomousSupervisor, SessionWorkBudget
except ImportError:
    from scripts.run_autonomous_supervisor import AutonomousSupervisor, SessionWorkBudget

STOP_REQUESTED = False

def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def _signal_stop(signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print(f"[WATCHDOG] stop requested by signal {signum}; finishing current bounded slice.")

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Courier's bounded idle-aware long-run watchdog.")
    p.add_argument("--hours", type=float, default=24.0, help="Total watchdog lifetime.")
    p.add_argument("--slice-seconds", type=float, default=900.0, help="Maximum wall-clock budget for one supervisor slice.")
    p.add_argument("--idle-sleep-seconds", type=float, default=300.0, help="Sleep between idle slices; consumes no model tokens.")
    p.add_argument("--max-operations-per-slice", type=int, default=12, help="Bounded useful operations per supervisor slice.")
    p.add_argument("--max-model-jobs", type=int, default=0, help="Total model-work reservations for the whole watchdog session.")
    p.add_argument("--max-external-actions", type=int, default=0, help="Total external-action reservations for the whole watchdog session.")
    p.add_argument("--zero-spend-limit-eur", type=float, default=0.0, help="Autonomous spend ceiling; defaults to zero.")
    p.add_argument("--host-gate-passed", action="store_true", help="Acknowledge the documented host-safety resume gate. Required for non-zero model/external budgets.")
    p.add_argument("--session-id", default=None, help="Stable session id; generated when omitted.")
    p.add_argument("--state-file", default=None, help="Optional durable watchdog state path.")
    p.add_argument("--once", action="store_true", help="Run one bounded slice only.")
    return p.parse_args()

def _validate(args: argparse.Namespace) -> None:
    if args.hours <= 0:
        raise SystemExit("--hours must be > 0")
    if args.slice_seconds <= 0:
        raise SystemExit("--slice-seconds must be > 0")
    if args.idle_sleep_seconds < 1:
        raise SystemExit("--idle-sleep-seconds must be >= 1")
    if args.max_operations_per_slice <= 0:
        raise SystemExit("--max-operations-per-slice must be > 0")
    if args.max_model_jobs < 0 or args.max_external_actions < 0:
        raise SystemExit("budgets must be >= 0")
    if args.zero_spend_limit_eur < 0:
        raise SystemExit("--zero-spend-limit-eur must be >= 0")
    if (args.max_model_jobs > 0 or args.max_external_actions > 0) and not args.host_gate_passed:
        raise SystemExit(
            "Non-zero autonomous model/external budgets require --host-gate-passed "
            "after the documented Courier resume gate is actually satisfied."
        )

def main() -> int:
    args = _parse_args()
    _validate(args)

    signal.signal(signal.SIGINT, _signal_stop)
    signal.signal(signal.SIGTERM, _signal_stop)

    session_id = args.session_id or (
        "watchdog-" + dt.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    )
    state_file = Path(args.state_file) if args.state_file else REPO_DIR / "events" / "longrun-watchdog" / f"{session_id}.json"

    started = time.monotonic()
    deadline = started + args.hours * 3600.0
    cycle = 0
    summaries: list[dict[str, Any]] = []

    state: dict[str, Any] = {
        "schema_version": "1.0",
        "session_id": session_id,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "started_at": _utc_now(),
        "deadline_hours": args.hours,
        "slice_seconds": args.slice_seconds,
        "idle_sleep_seconds": args.idle_sleep_seconds,
        "max_operations_per_slice": args.max_operations_per_slice,
        "max_model_jobs": args.max_model_jobs,
        "max_external_actions": args.max_external_actions,
        "zero_spend_limit_eur": args.zero_spend_limit_eur,
        "host_gate_passed": bool(args.host_gate_passed),
        "cycles": 0,
        "status": "RUNNING",
        "last_stop_reason": None,
        "last_summary": None,
    }
    _write_json_atomic(state_file, state)

    print("=" * 72)
    print("COURIER LONG-RUN WATCHDOG")
    print(f"session={session_id}")
    print(f"lifetime={args.hours}h slice={args.slice_seconds}s idle_sleep={args.idle_sleep_seconds}s")
    print(f"model_budget={args.max_model_jobs} external_budget={args.max_external_actions} spend_limit={args.zero_spend_limit_eur:.2f} EUR")
    print(f"state={state_file}")
    print("=" * 72)

    supervisor = AutonomousSupervisor(repo_dir=REPO_DIR)

    while not STOP_REQUESTED and time.monotonic() < deadline:
        cycle += 1
        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0:
            break

        slice_seconds = min(args.slice_seconds, remaining)
        budget = SessionWorkBudget(
            max_wall_clock_seconds=slice_seconds,
            max_active_tasks=1,
            heavy_job_limit=1,
            max_consecutive_failures=2,
            max_retries_per_task=2,
            max_queue_size=50,
            max_model_work_budget=args.max_model_jobs,
            max_external_actions=args.max_external_actions,
            zero_spend_limit_eur=args.zero_spend_limit_eur,
        )

        print(f"\n[WATCHDOG] cycle={cycle} remaining={remaining:.0f}s")
        try:
            summary = supervisor.run_long_run_session(
                budget=budget,
                session_id=session_id,
                enable_bundling=True,
                max_bundle_size=3,
                max_operations=args.max_operations_per_slice,
                idle_exit_after_empty_checks=2,
            )
        except Exception as exc:
            summary = {
                "status": "WATCHDOG_SLICE_EXCEPTION",
                "stop_reason": type(exc).__name__,
                "error": str(exc),
            }
            print(f"[WATCHDOG] slice exception: {type(exc).__name__}: {exc}")

        summaries.append(summary)
        if len(summaries) > 20:
            summaries = summaries[-20:]

        stop_reason = str(summary.get("stop_reason") or "")
        state.update({
            "cycles": cycle,
            "updated_at": _utc_now(),
            "last_stop_reason": stop_reason,
            "last_summary": summary,
            "recent_summaries": summaries,
        })
        _write_json_atomic(state_file, state)

        if args.once or STOP_REQUESTED:
            break

        if stop_reason in {"GLOBAL_CIRCUIT_OPEN", "FAILED_CIRCUIT_OPEN", "PAYMENT_APPROVAL_REQUIRED"}:
            print(f"[WATCHDOG] fail-closed stop: {stop_reason}")
            state["status"] = "PAUSED_FAIL_CLOSED"
            _write_json_atomic(state_file, state)
            break

        sleep_for = min(args.idle_sleep_seconds, max(0.0, deadline - time.monotonic()))
        if sleep_for <= 0:
            break
        print(f"[WATCHDOG] idle sleep {sleep_for:.0f}s (no model work)")
        end_sleep = time.monotonic() + sleep_for
        while not STOP_REQUESTED and time.monotonic() < end_sleep:
            time.sleep(min(1.0, end_sleep - time.monotonic()))

    if STOP_REQUESTED:
        final_status = "STOPPED_BY_SIGNAL"
    elif state.get("status") == "PAUSED_FAIL_CLOSED":
        final_status = "PAUSED_FAIL_CLOSED"
    else:
        final_status = "DEADLINE_REACHED"

    state.update({"updated_at": _utc_now(), "finished_at": _utc_now(), "status": final_status})
    _write_json_atomic(state_file, state)
    print(f"[WATCHDOG] finished: {final_status} after {cycle} cycles")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
