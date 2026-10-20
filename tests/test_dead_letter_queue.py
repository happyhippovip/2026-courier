"""Tests for Dead-Letter Queue Inspector and Auto-Retrier."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from courier_core.dead_letter_queue import (
    DeadLetterQueue,
    DLQEntry,
    CorruptDLQError,
    record_failure,
    get_retryable_items,
    quarantine_item,
    replay_item,
    audit_quarantine,
    main,
)


def test_initial_failure_marks_retryable_with_backoff(tmp_path):
    dlq_file = tmp_path / "dlq.json"
    dlq = DeadLetterQueue(dlq_path=str(dlq_file), max_attempts=3, backoff_base_sec=2.0)

    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    entry = dlq.record_failure(
        item_id="P19_task_1",
        error_reason="Timeout during provider connection",
        attempts=1,
        now=now,
    )

    assert entry.item_id == "P19_task_1"
    assert entry.state == "RETRYABLE"
    assert entry.attempts == 1
    # backoff: 2.0 ** 1 = 2.0 seconds
    expected_retry = now + timedelta(seconds=2.0)
    assert entry.retry_after == expected_retry.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_exceeded_attempts_moves_to_quarantine(tmp_path):
    dlq_file = tmp_path / "dlq.json"
    dlq = DeadLetterQueue(dlq_path=str(dlq_file), max_attempts=3)

    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    entry = dlq.record_failure(
        item_id="P19_task_fail",
        error_reason="Persistent OOM crash",
        attempts=3,
        now=now,
    )

    assert entry.state == "QUARANTINED"
    assert entry.attempts == 3
    assert entry.retry_after is None


def test_non_idempotent_failure_quarantined_immediately(tmp_path):
    dlq_file = tmp_path / "dlq_non_idemp.json"
    dlq = DeadLetterQueue(dlq_path=str(dlq_file), max_attempts=3)
    entry = dlq.record_failure(
        item_id="P19_non_idempotent",
        error_reason="Timeout after partial side effect",
        attempts=1,
        idempotent=False,
    )
    assert entry.state == "QUARANTINED"
    assert entry.retry_after is None


def test_get_retryable_items_evaluates_time_window(tmp_path):
    dlq_file = tmp_path / "dlq.json"
    dlq = DeadLetterQueue(dlq_path=str(dlq_file), max_attempts=3, backoff_base_sec=10.0)

    t0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    dlq.record_failure("item_early", "Err1", attempts=1, now=t0)  # retry at t0 + 10s
    dlq.record_failure("item_late", "Err2", attempts=2, now=t0)   # retry at t0 + 100s

    # At t0 + 5s: none should be ready
    t_5 = t0 + timedelta(seconds=5)
    ready_5 = dlq.get_retryable_items(now=t_5)
    assert len(ready_5) == 0

    # At t0 + 15s: item_early should be ready
    t_15 = t0 + timedelta(seconds=15)
    ready_15 = dlq.get_retryable_items(now=t_15)
    assert len(ready_15) == 1
    assert ready_15[0].item_id == "item_early"

    # At t0 + 120s: both should be ready
    t_120 = t0 + timedelta(seconds=120)
    ready_120 = dlq.get_retryable_items(now=t_120)
    assert len(ready_120) == 2


def test_manual_quarantine_and_replay(tmp_path):
    dlq_file = tmp_path / "dlq.json"
    dlq = DeadLetterQueue(dlq_path=str(dlq_file))

    dlq.record_failure("item_poison", "Corrupt payload", attempts=1)
    entry = dlq.quarantine_item("item_poison", reason="Manual operator quarantine")
    assert entry.state == "QUARANTINED"
    assert "Manual operator quarantine" in entry.error_reason

    # Replay resets attempts and marks retryable
    replayed = dlq.replay_item("item_poison")
    assert replayed.state == "RETRYABLE"
    assert replayed.attempts == 0
    assert replayed.retry_after is not None


def test_audit_quarantine_summary(tmp_path):
    dlq_file = tmp_path / "dlq.json"
    dlq = DeadLetterQueue(dlq_path=str(dlq_file))

    dlq.record_failure("item_1", "NetworkTimeout", attempts=1)
    dlq.record_failure("item_2", "NetworkTimeout", attempts=1)
    dlq.record_failure("item_3", "SyntaxError", attempts=3)

    summary = dlq.audit()
    assert summary["total_entries"] == 3
    assert summary["quarantined_count"] == 1
    assert summary["retryable_count"] == 2
    assert summary["reasons"]["NetworkTimeout"] == 2
    assert summary["reasons"]["SyntaxError"] == 1


def test_persistence_reload_consistency(tmp_path):
    dlq_file = tmp_path / "dlq.json"
    dlq1 = DeadLetterQueue(dlq_path=str(dlq_file))
    dlq1.record_failure("persisted_item", "Fatal error", attempts=3)

    # Reload from disk
    dlq2 = DeadLetterQueue(dlq_path=str(dlq_file))
    assert "persisted_item" in dlq2.entries
    assert dlq2.entries["persisted_item"].state == "QUARANTINED"


def test_cli_invocation(tmp_path):
    dlq_file = tmp_path / "cli_dlq.json"

    # 1. Record via CLI
    code1 = main([
        "record",
        "--item", "cli_task",
        "--reason", "CLI error",
        "--attempts", "1",
        "--dlq-file", str(dlq_file),
    ])
    assert code1 == 0

    # 2. Audit via CLI
    code2 = main([
        "audit",
        "--dlq-file", str(dlq_file),
    ])
    assert code2 == 0

    # 3. Quarantine via CLI
    code3 = main([
        "quarantine",
        "--item", "cli_task",
        "--reason", "Poison message",
        "--dlq-file", str(dlq_file),
    ])
    assert code3 == 0

    data = json.loads(dlq_file.read_text(encoding="utf-8"))
    assert data["cli_task"]["state"] == "QUARANTINED"


def test_corrupt_dlq_file_raises_instead_of_silent_reset(tmp_path):
    dlq_file = tmp_path / "dlq_corrupt.json"
    dlq_file.write_text("{broken json", encoding="utf-8")
    with pytest.raises(CorruptDLQError, match="Corrupt DLQ file"):
        DeadLetterQueue(dlq_path=str(dlq_file))


def test_symlink_dlq_file_load_and_save_refused(tmp_path, monkeypatch):
    symlink_file = tmp_path / "dlq_link.json"
    symlink_file.write_text('{"a": 1}', encoding="utf-8")
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self == symlink_file else False)

    with pytest.raises(CorruptDLQError, match="refusing insecure load"):
        DeadLetterQueue(dlq_path=str(symlink_file))


def test_atomic_save_fsync_and_retry_resilience(tmp_path, monkeypatch):
    import os
    dlq_file = tmp_path / "dlq_flaky.json"
    dlq = DeadLetterQueue(dlq_path=str(dlq_file))

    attempts = {"count": 0}
    real_replace = os.replace

    def flaky_replace(src, dst):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("Simulated transient Windows file lock")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    dlq.record_failure("retry_task", "Transient network blip", attempts=1)
    assert attempts["count"] == 3
    assert dlq_file.exists()
    reloaded = DeadLetterQueue(dlq_path=str(dlq_file))
    assert "retry_task" in reloaded.entries
