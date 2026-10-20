"""Tests for Unified Worker Daemon Runtime with Resilience Wiring."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.worker_daemon import (
    WorkerDaemon,
    TaskCycleResult,
    main,
)


def test_successful_task_cycle_signs_receipt(tmp_path):
    outbox = tmp_path / "outbox"
    crashes = tmp_path / "crashes"
    dlq_file = tmp_path / "dlq.json"

    daemon = WorkerDaemon(
        worker_id="windows-titan",
        secret_key="daemon-secret-key-2026",
        outbox_dir=str(outbox),
        crash_dir=str(crashes),
        dlq_file=str(dlq_file),
        cost_limit_eur=0.0,
    )

    def sample_handler():
        return {"status": "DONE", "output": "Artifacts verified"}

    cost_spec = {"provider": "local_titan", "model": "v30", "cost_estimate_eur": 0.0}
    res = daemon.execute_task_cycle(item_id="P21_task_1", handler_fn=sample_handler, cost_spec=cost_spec)

    assert res.status == "SUCCESS"
    assert res.signed_receipt is not None
    assert res.signed_receipt.signature.startswith("hmac-sha256:")
    assert res.signed_receipt.payload["output"] == "Artifacts verified"

    # Verify receipt written to outbox
    receipt_files = list(outbox.glob("*.json"))
    assert len(receipt_files) == 1
    disk_data = json.loads(receipt_files[0].read_text(encoding="utf-8"))
    assert disk_data["signature"] == res.signed_receipt.signature


def test_cost_gate_breach_blocks_handler_execution(tmp_path):
    executed = False

    def expensive_handler():
        nonlocal executed
        executed = True
        return {"status": "DONE"}

    daemon = WorkerDaemon(
        worker_id="windows-titan",
        secret_key="daemon-secret-key-2026",
        work_dir=str(tmp_path),
        cost_limit_eur=0.0,
    )

    cost_spec = {"provider": "cloud_openai", "model": "gpt-4o", "cost_estimate_eur": 0.05}
    res = daemon.execute_task_cycle(item_id="P21_task_expensive", handler_fn=expensive_handler, cost_spec=cost_spec)

    assert res.status == "COST_GATE_BLOCKED"
    assert executed is False
    assert res.signed_receipt is None
    assert "AUTONOMOUS_SPEND_LIMIT_EXCEEDED" in res.error_message


def test_unknown_cost_spec_is_strictly_blocked(tmp_path):
    executed = False

    def unmetered_handler():
        nonlocal executed
        executed = True
        return {"status": "DONE"}

    daemon = WorkerDaemon(
        worker_id="windows-titan",
        secret_key="daemon-secret-key-2026",
        work_dir=str(tmp_path),
        cost_limit_eur=0.0,
    )

    # Missing estimated_cost_eur or unknown
    res = daemon.execute_task_cycle(item_id="P21_task_unknown", handler_fn=unmetered_handler, cost_spec={})

    assert res.status == "COST_GATE_BLOCKED"
    assert executed is False
    assert res.error_message in ("INVALID_SPEC", "UNKNOWN_COST_BLOCKED")


def test_none_cost_spec_strictly_blocks_and_never_defaults_to_zero(tmp_path):
    executed = False

    def handler():
        nonlocal executed
        executed = True
        return {"status": "DONE"}

    daemon = WorkerDaemon(
        worker_id="windows-titan",
        secret_key="daemon-secret-key-2026",
        work_dir=str(tmp_path),
        cost_limit_eur=0.0,
    )

    # Calling execute_task_cycle with cost_spec=None must be BLOCKED
    res = daemon.execute_task_cycle(item_id="P21_cost_none", handler_fn=handler, cost_spec=None)

    assert res.status == "COST_GATE_BLOCKED"
    assert executed is False
    assert res.error_message == "UNKNOWN_COST_BLOCKED"


def test_exception_in_handler_triggers_crash_harvest_and_dlq(tmp_path):
    crashes = tmp_path / "crashes"
    dlq_file = tmp_path / "dlq.json"

    daemon = WorkerDaemon(
        worker_id="windows-titan",
        secret_key="daemon-secret-key-2026",
        crash_dir=str(crashes),
        dlq_file=str(dlq_file),
    )

    def failing_handler():
        token = "Bearer secret-leaked-token-12345"
        raise ValueError(f"Crash occurred with auth: {token}")

    authorized_spec = {"provider": "local_titan", "model": "v30", "cost_estimate_eur": 0.0}
    res = daemon.execute_task_cycle(item_id="P21_task_fail", handler_fn=failing_handler, cost_spec=authorized_spec)

    assert res.status == "FAILED"
    assert res.crash_report is not None
    assert res.crash_report.category == "EXCEPTION"
    # Verify credential scrubbing in crash report
    assert "secret-leaked-token-12345" not in res.crash_report.error_message
    assert "secret-leaked-token-12345" not in res.crash_report.traceback_cleaned
    assert "[REDACTED]" in res.crash_report.error_message

    # Verify DLQ entry created
    assert res.dlq_entry is not None
    assert res.dlq_entry.state == "RETRYABLE"
    assert res.dlq_entry.attempts == 1

    # Verify crash file on disk
    crash_files = list(crashes.glob("*.json"))
    assert len(crash_files) == 1

    # Handler returning {"status": "FAILED"} without raising must also be treated as FAILED, never signed as SUCCESS
    res_dict_fail = daemon.execute_task_cycle(
        item_id="P21_task_dict_fail",
        handler_fn=lambda: {"status": "FAILED", "error": "Verifier rejected output"},
        cost_spec=authorized_spec,
    )
    assert res_dict_fail.status == "FAILED"
    assert res_dict_fail.signed_receipt is None


def test_resource_pressure_aborts_execution(tmp_path, monkeypatch):
    executed = False

    def handler():
        nonlocal executed
        executed = True
        return {"status": "DONE"}

    # Mock resource watchdog to simulate high memory pressure
    from courier_core import resource_watchdog
    def fake_resource_health(*args, **kwargs):
        return resource_watchdog.ResourceHealthReport(
            state="PRESSURED",
            rss_mb=5000.0,
            open_fds=10,
            pressure_reasons=["memory-pressure"],
            cooldown_remaining_s=0.0,
        )
    monkeypatch.setattr("courier_core.worker_daemon.evaluate_resource_health", fake_resource_health)

    daemon = WorkerDaemon(
        worker_id="windows-titan",
        secret_key="daemon-secret-key-2026",
        work_dir=str(tmp_path),
    )

    res = daemon.execute_task_cycle(item_id="P21_task_pressure", handler_fn=handler)
    assert res.status == "RESOURCE_PRESSURE"
    assert executed is False
    assert "memory-pressure" in res.error_message


def test_cli_invocation_healthy(tmp_path):
    outbox = tmp_path / "cli_outbox"
    crashes = tmp_path / "cli_crashes"

    code = main([
        "--item", "P21_cli_task",
        "--worker-id", "windows-titan",
        "--key", "cli-key-2026",
        "--outbox", str(outbox),
        "--crashes", str(crashes),
        "--mock-success",
    ])
    assert code == 0
    assert outbox.exists()
    receipts = list(outbox.glob("*.json"))
    assert len(receipts) == 1
