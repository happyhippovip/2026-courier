import hashlib
import json
import os
import sys
import time
from pathlib import Path
from unittest import mock
import pytest

from courier_core.work_packet import PacketQueue, PacketState, WorkPacket
from scripts.google_builder_worker import (
    acquire_packet_lock,
    execute_packet_code_or_test_work,
    get_current_git_sha,
    is_host_safe,
    lock_path,
    probe_integration_surface,
    process_work_packet,
    release_packet_lock,
    run_google_builder_queue,
)
from scripts.run_antigravity_bridge import (
    AntigravityHookRunner,
    AntigravityVisualStateTracker,
)


def test_probe_integration_surface():
    surface = probe_integration_surface()
    assert "has_agy_cli" in surface
    assert "has_api_key" in surface
    assert "authorized_mode" in surface
    assert surface["zero_cost_policy"] == "ZERO_COST_ONLY"
    assert surface["human_gate_policy"] == "STOP_ON_HUMAN_GATE_ONLY"
    assert "Google subscription does not grant raw API automation" in surface["account_entitlement_note"]


def test_packet_lock_lifecycle(tmp_path):
    packet_id = "test-packet-001"
    lock_dir = tmp_path / "locks"

    # Acquire initial lock
    assert acquire_packet_lock(packet_id, lock_dir=lock_dir) is True
    assert lock_path(packet_id, lock_dir=lock_dir).exists()

    # Second acquire should fail (single-writer mutual exclusion)
    assert acquire_packet_lock(packet_id, lock_dir=lock_dir) is False

    # Release lock
    release_packet_lock(packet_id, lock_dir=lock_dir)
    assert not lock_path(packet_id, lock_dir=lock_dir).exists()

    # Re-acquire succeeds
    assert acquire_packet_lock(packet_id, lock_dir=lock_dir) is True
    release_packet_lock(packet_id, lock_dir=lock_dir)


def test_stale_lock_stealing(tmp_path):
    packet_id = "test-packet-stale"
    lock_dir = tmp_path / "locks"
    lpath = lock_path(packet_id, lock_dir=lock_dir)
    lpath.parent.mkdir(parents=True, exist_ok=True)

    # Write a stale lock (> 300s old)
    stale_data = {
        "pid": 999999,
        "packet_id": packet_id,
        "started_at": time.time() - 400,
        "worker_id": "other-worker",
    }
    lpath.write_text(json.dumps(stale_data), encoding="utf-8")

    # Acquire should steal the stale lock
    assert acquire_packet_lock(packet_id, lock_dir=lock_dir, timeout_seconds=300) is True
    release_packet_lock(packet_id, lock_dir=lock_dir)


CALM_HOST = lambda: {"memory_percent": 40.0, "swap_percent": 10.0}  # noqa: E731


def test_host_safe_checks(tmp_path, monkeypatch):
    assert is_host_safe(tmp_path, sampler=CALM_HOST) is True

    # Host STOP file
    stop_file = tmp_path / "events/STOP"
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.write_text("STOP")
    assert is_host_safe(tmp_path, sampler=CALM_HOST) is False

    stop_file.unlink()
    assert is_host_safe(tmp_path, sampler=CALM_HOST) is True

    # Environment flag
    monkeypatch.setenv("COURIER_STOP", "1")
    assert is_host_safe(tmp_path, sampler=CALM_HOST) is False


def test_sha_mismatch_supersedes_packet(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    packet = WorkPacket(
        id="task-stale-sha",
        owner_id="google-mac",
        target_sha="sha_stale_12345",
        state=PacketState.CURRENT,
        payload={"task_type": "verify_file"},
    )

    final_packet, result_file, decision = process_work_packet(
        packet=packet,
        repo_dir=tmp_path,
        current_sha="sha_current_67890",
        host_safe=True,
        lock_dir=tmp_path / "locks",
    )

    assert final_packet.state == PacketState.SUPERSEDED
    assert result_file is None
    assert decision is None

    # Verify central_state recorded SKIPPED
    with open(tmp_path / "central_state.json", "r") as f:
        state = json.load(f)
    assert state["tasks"]["task-stale-sha"]["reconciled_status"] == "SKIPPED"


def test_host_unsafe_parks_packet(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    packet = WorkPacket(
        id="task-park-host",
        owner_id="google-mac",
        target_sha="sha_exact_12345",
        state=PacketState.CURRENT,
        payload={"task_type": "verify_file"},
    )

    final_packet, result_file, decision = process_work_packet(
        packet=packet,
        repo_dir=tmp_path,
        current_sha="sha_exact_12345",
        host_safe=False,
        lock_dir=tmp_path / "locks",
    )

    assert final_packet.state == PacketState.PARKED_BY_HOST
    assert result_file is None
    assert decision is None


def test_scope_escape_rejected(tmp_path):
    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)
    surface = probe_integration_surface()

    packet = WorkPacket(
        id="task-escape",
        owner_id="google-mac",
        target_sha="sha1",
        state=PacketState.CURRENT,
        payload={"allowed_scope": ["../../etc/passwd"], "task_type": "verify_file"},
    )

    with pytest.raises(ValueError, match="escapes repository root"):
        execute_packet_code_or_test_work(packet, tmp_path, hooks, surface)


def test_execute_verify_file_task(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.google_builder_worker.EVIDENCE_DIR", tmp_path / "events/evidence")
    test_file = tmp_path / "contract.txt"
    test_file.write_text("Hello Courier Contract", encoding="utf-8")

    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)
    surface = probe_integration_surface()

    packet = WorkPacket(
        id="task-verify-ok",
        owner_id="google-mac",
        target_sha="sha1",
        state=PacketState.CURRENT,
        payload={
            "task_type": "verify_file",
            "target_file": "contract.txt",
            "allowed_scope": ["contract.txt"],
        },
    )

    result = execute_packet_code_or_test_work(packet, tmp_path, hooks, surface)
    assert result["verdict"] == "PASS"
    assert result["action_executed"] == "verify_file"
    assert (tmp_path / result["evidence_file"]).exists()

    evidence = json.loads((tmp_path / result["evidence_file"]).read_text(encoding="utf-8"))
    assert evidence["file_sha256"] == hashlib.sha256(b"Hello Courier Contract").hexdigest()


def test_execute_run_tests_task(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.google_builder_worker.EVIDENCE_DIR", tmp_path / "events/evidence")

    tracker = AntigravityVisualStateTracker(repo_dir=tmp_path)
    hooks = AntigravityHookRunner(tracker)
    surface = probe_integration_surface()

    packet = WorkPacket(
        id="task-test-ok",
        owner_id="google-mac",
        target_sha="sha1",
        state=PacketState.CURRENT,
        payload={
            "task_type": "run_tests",
            "command": [sys.executable, "-c", "import sys; print('TEST_PASS'); sys.exit(0)"],
            "allowed_scope": ["tests/"],
        },
    )

    result = execute_packet_code_or_test_work(packet, tmp_path, hooks, surface)
    assert result["verdict"] == "PASS"
    assert result["action_executed"] == "run_tests"
    assert (tmp_path / result["evidence_file"]).exists()


def test_two_distinct_units_sequential_execution(tmp_path, monkeypatch):
    """Proves two distinct safe logical work units execute and record autonomously.

    Dennis is NOT the message bus: Unit 1 completes and verifies, whereupon Unit 2
    is automatically promoted and executed.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("scripts.google_builder_worker.EVIDENCE_DIR", tmp_path / "events/evidence")
    monkeypatch.setattr("scripts.run_antigravity_bridge.PROCESSED_DIR", tmp_path / "events/processed")
    monkeypatch.setattr("scripts.run_antigravity_bridge.DECISIONS_DIR", tmp_path / "events/chief-decisions")

    file_a = tmp_path / "file_a.txt"
    file_a.write_text("Work Unit A Source Data", encoding="utf-8")

    file_b = tmp_path / "file_b.txt"
    file_b.write_text("Work Unit B Source Data", encoding="utf-8")

    current_sha = "f425d3285611333d81cfffa263deebba186e398c"

    # Queue with two distinct units: Unit 1 is CURRENT, Unit 2 is NEXT
    queue = PacketQueue()

    unit1 = WorkPacket(
        id="work-unit-1-test",
        owner_id="google-mac",
        target_sha=current_sha,
        state=PacketState.CURRENT,
        payload={
            "task_type": "run_tests",
            "instruction": "Execute targeted invariant check",
            "command": [sys.executable, "-c", "import sys; print('INVARIANT_A_VERIFIED'); sys.exit(0)"],
            "allowed_scope": ["file_a.txt"],
        },
    )

    unit2 = WorkPacket(
        id="work-unit-2-verify",
        owner_id="google-mac",
        target_sha=current_sha,
        state=PacketState.NEXT,
        payload={
            "task_type": "verify_file",
            "instruction": "Verify file B contract",
            "target_file": "file_b.txt",
            "allowed_scope": ["file_b.txt"],
        },
    )

    queue.add_packet(unit1)
    queue.add_packet(unit2)

    records = run_google_builder_queue(
        queue=queue,
        repo_dir=tmp_path,
        current_sha=current_sha,
        max_units=5,
        host_safe=True,
        lock_dir=tmp_path / "events/locks",
    )

    # Both units executed sequentially
    assert len(records) == 2
    assert records[0]["packet_id"] == "work-unit-1-test"
    assert records[0]["decision"]["verdict"] == "ACCEPTED"
    assert records[0]["decision"]["action"] == "AUTO_APPROVE_SAFE_RESULT"

    assert records[1]["packet_id"] == "work-unit-2-verify"
    assert records[1]["decision"]["verdict"] == "ACCEPTED"
    assert records[1]["decision"]["action"] == "AUTO_APPROVE_SAFE_RESULT"

    # Verify both result envelopes exist
    res1_path = tmp_path / "events/processed/work-unit-1-test-result.json"
    res2_path = tmp_path / "events/processed/work-unit-2-verify-result.json"
    assert res1_path.exists()
    assert res2_path.exists()

    res1_data = json.loads(res1_path.read_text(encoding="utf-8"))
    res2_data = json.loads(res2_path.read_text(encoding="utf-8"))
    assert res1_data["payload"]["verdict"] == "PASS"
    assert res2_data["payload"]["verdict"] == "PASS"
    assert res1_data["payload"]["action_executed"] == "run_tests"
    assert res2_data["payload"]["action_executed"] == "verify_file"

    # Verify both distinct evidence files exist with distinct digests
    ev1_path = tmp_path / res1_data["payload"]["evidence_file"]
    ev2_path = tmp_path / res2_data["payload"]["evidence_file"]
    assert ev1_path.exists()
    assert ev2_path.exists()
    assert res1_data["payload"]["evidence_sha256"] != res2_data["payload"]["evidence_sha256"]

    # Verify central_state recorded both tasks
    with open(tmp_path / "central_state.json", "r") as f:
        central = json.load(f)
    assert central["tasks"]["work-unit-1-test"]["reconciled_status"] == "SUCCESS"
    assert central["tasks"]["work-unit-2-verify"]["reconciled_status"] == "SUCCESS"
