#!/usr/bin/env python3
"""Bounded, idle-aware wrapper for Courier's autonomous supervisor."""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import gc
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
    p.add_argument("--idle-sleep-seconds", type=float, default=300.0, help="Initial sleep between idle slices; consumes no model tokens.")
    p.add_argument("--idle-sleep-max-seconds", type=float, default=1800.0, help="Maximum adaptive idle sleep.")
    p.add_argument("--error-backoff-seconds", type=float, default=600.0, help="Backoff after a non-resource slice exception.")
    p.add_argument("--resource-backoff-seconds", type=float, default=1800.0, help="Backoff after EMFILE/ENFILE/resource pressure.")
    p.add_argument("--max-consecutive-slice-errors", type=int, default=3, help="Fail closed after this many consecutive slice exceptions.")
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
    if args.idle_sleep_max_seconds < args.idle_sleep_seconds:
        raise SystemExit("--idle-sleep-max-seconds must be >= --idle-sleep-seconds")
    if args.error_backoff_seconds < 1 or args.resource_backoff_seconds < 1:
        raise SystemExit("backoff seconds must be >= 1")
    if args.max_consecutive_slice_errors <= 0:
        raise SystemExit("--max-consecutive-slice-errors must be > 0")
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


def _is_resource_pressure(exc: BaseException) -> bool:
    if isinstance(exc, OSError) and exc.errno in {errno.EMFILE, errno.ENFILE}:
        return True
    text = str(exc).lower()
    return "too many open files" in text or "emfile" in text or "enfile" in text

def _sleep_interruptibly(seconds: float) -> None:
    end_sleep = time.monotonic() + max(0.0, seconds)
    while not STOP_REQUESTED and time.monotonic() < end_sleep:
        time.sleep(min(1.0, max(0.0, end_sleep - time.monotonic())))

def _idle_backoff(base: float, maximum: float, idle_streak: int) -> float:
    # 5m, 10m, 20m, then capped (default 30m). This prevents empty-queue
    # polling from becoming a token/process churn loop.
    exponent = max(0, idle_streak - 1)
    return min(maximum, base * (2 ** exponent))

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
    idle_streak = 0
    consecutive_slice_errors = 0
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
        "idle_sleep_max_seconds": args.idle_sleep_max_seconds,
        "error_backoff_seconds": args.error_backoff_seconds,
        "resource_backoff_seconds": args.resource_backoff_seconds,
        "max_consecutive_slice_errors": args.max_consecutive_slice_errors,
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
        slice_exception: BaseException | None = None
        try:
            # Fresh supervisor per bounded slice: reduces long-lived in-memory state
            # accumulation and makes each cycle recover from durable repository state.
            supervisor = AutonomousSupervisor(repo_dir=REPO_DIR)
            summary = supervisor.run_long_run_session(
                budget=budget,
                session_id=session_id,
                enable_bundling=True,
                max_bundle_size=3,
                max_operations=args.max_operations_per_slice,
                idle_exit_after_empty_checks=2,
            )
        except Exception as exc:
            slice_exception = exc
            summary = {
                "status": "WATCHDOG_SLICE_EXCEPTION",
                "stop_reason": "RESOURCE_PRESSURE" if _is_resource_pressure(exc) else type(exc).__name__,
                "error": str(exc),
            }
            print(f"[WATCHDOG] slice exception: {type(exc).__name__}: {exc}")
        finally:
            # Best-effort collection only; never spawn cleanup subprocesses here.
            if "supervisor" in locals():
                del supervisor
            gc.collect()

        summaries.append(summary)
        if len(summaries) > 20:
            summaries = summaries[-20:]

        stop_reason = str(summary.get("stop_reason") or "")
        useful_ops = int(summary.get("total_operations_completed") or 0)
        if slice_exception is not None:
            consecutive_slice_errors += 1
        else:
            consecutive_slice_errors = 0

        if useful_ops > 0:
            idle_streak = 0
        elif stop_reason == "IDLE_MONITORING_NO_WORK":
            idle_streak += 1
        else:
            idle_streak = 0

        state.update({
            "cycles": cycle,
            "updated_at": _utc_now(),
            "last_stop_reason": stop_reason,
            "last_summary": summary,
            "recent_summaries": summaries,
            "idle_streak": idle_streak,
            "consecutive_slice_errors": consecutive_slice_errors,
        })
        _write_json_atomic(state_file, state)

        if args.once or STOP_REQUESTED:
            break

        if stop_reason in {"GLOBAL_CIRCUIT_OPEN", "FAILED_CIRCUIT_OPEN", "PAYMENT_APPROVAL_REQUIRED"}:
            print(f"[WATCHDOG] fail-closed stop: {stop_reason}")
            state["status"] = "PAUSED_FAIL_CLOSED"
            _write_json_atomic(state_file, state)
            break

        if consecutive_slice_errors >= args.max_consecutive_slice_errors:
            print(f"[WATCHDOG] fail-closed after {consecutive_slice_errors} consecutive slice errors")
            state["status"] = "PAUSED_FAIL_CLOSED"
            state["last_stop_reason"] = "CONSECUTIVE_SLICE_ERRORS"
            _write_json_atomic(state_file, state)
            break

        if slice_exception is not None and _is_resource_pressure(slice_exception):
            requested_sleep = args.resource_backoff_seconds
            sleep_reason = "resource backoff"
        elif slice_exception is not None:
            requested_sleep = args.error_backoff_seconds
            sleep_reason = "error backoff"
        elif stop_reason == "IDLE_MONITORING_NO_WORK":
            requested_sleep = _idle_backoff(
                args.idle_sleep_seconds, args.idle_sleep_max_seconds, idle_streak
            )
            sleep_reason = f"adaptive idle backoff streak={idle_streak}"
        else:
            requested_sleep = args.idle_sleep_seconds
            sleep_reason = "normal inter-slice rest"

        sleep_for = min(requested_sleep, max(0.0, deadline - time.monotonic()))
        if sleep_for <= 0:
            break
        state["next_check_after_seconds"] = sleep_for
        state["sleep_reason"] = sleep_reason
        _write_json_atomic(state_file, state)
        print(f"[WATCHDOG] sleep {sleep_for:.0f}s ({sleep_reason}; no model work)")
        _sleep_interruptibly(sleep_for)

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
