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


def test_bool_lock_timestamp_is_not_stolen(tmp_path):
    """True is not a time. A bool started_at must not look ancient and be stolen."""
    packet_id = "test-packet-bool"
    lock_dir = tmp_path / "locks"
    lpath = lock_path(packet_id, lock_dir=lock_dir)
    lpath.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps({
        "pid": 999999,
        "packet_id": packet_id,
        "started_at": True,
        "worker_id": "other-worker",
    })
    lpath.write_text(original, encoding="utf-8")
    owned = acquire_packet_lock(packet_id, lock_dir=lock_dir, timeout_seconds=300)
    assert owned is False, lpath.read_text(encoding="utf-8")
    assert lpath.read_text(encoding="utf-8") == original
    false_body = json.dumps({
        "pid": 999999,
        "packet_id": packet_id,
        "started_at": False,
        "worker_id": "other-worker",
    })
    lpath.write_text(false_body, encoding="utf-8")
    assert acquire_packet_lock(packet_id, lock_dir=lock_dir, timeout_seconds=300) is False
    assert lpath.read_text(encoding="utf-8") == false_body


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


def test_google_agent_task_costgate_enforced(tmp_path):
    """Proves P0 CostGate fail-closed guard before Google agent spawn."""
    from scripts.google_builder_worker import run_google_agent_task

    evidence = {}
    surface = {"has_agy_cli": True}

    # 1. Positive cost without human gate -> blocked
    payload_spend = {
        "workkey": "WK-SPEND",
        "instruction": "do something paid",
        "estimated_cost_eur": 5.0,
    }
    verdict = run_google_agent_task(payload_spend, tmp_path, evidence, surface)
    assert verdict == "FAILED"
    assert "COST_GATE_DENIED" in evidence.get("blocked_reason", "")
    assert evidence.get("provider_invoked") is False

    # 2. NaN / invalid cost -> blocked
    payload_nan = {
        "workkey": "WK-NAN",
        "instruction": "do something invalid",
        "estimated_cost_eur": float("nan"),
    }
    evidence_nan = {}
    verdict = run_google_agent_task(payload_nan, tmp_path, evidence_nan, surface)
    assert verdict == "FAILED"
    assert "COST_GATE_DENIED" in evidence_nan.get("blocked_reason", "")
    assert evidence_nan.get("provider_invoked") is False

    # 3. Missing estimated_cost_eur -> blocked (UNKNOWN_COST)
    payload_missing = {
        "workkey": "WK-MISSING-COST",
        "instruction": "do something unestimated",
    }
    evidence_missing = {}
    verdict = run_google_agent_task(payload_missing, tmp_path, evidence_missing, surface)
    assert verdict == "FAILED"
    assert "COST_GATE_DENIED" in evidence_missing.get("blocked_reason", "")
    assert "UNKNOWN_COST" in evidence_missing.get("blocked_reason", "")
    assert evidence_missing.get("provider_invoked") is False


def test_bool_timeout_does_not_invoke_the_agent(tmp_path):
    from scripts.google_builder_worker import run_google_agent_task

    evidence = {}
    payload = {
        "workkey": "WK-BOOL",
        "instruction": "do something local",
        "estimated_cost_eur": 0.0,
        "timeout_seconds": True,
    }
    with mock.patch("scripts.google_builder_worker.AGENT_RUNNER") as runner:
        verdict = run_google_agent_task(payload, tmp_path, evidence, {"has_agy_cli": True})
    runner.assert_not_called()
    assert verdict == "FAILED"
    assert evidence.get("provider_invoked") is False


class _Hooks:
    def on_tool_action(self, *args, **kwargs):
        return None


def _packet(packet_id):
    return WorkPacket(
        id=packet_id,
        owner_id="local",
        target_sha="abc",
        state=PacketState.CURRENT,
        payload={"task_type": "deterministic_transform", "input": "hello"},
    )


def test_evidence_does_not_follow_a_symlinked_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        (repo / "events").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Creating symlinks on Windows requires developer mode or administrator privilege")
        raise
    try:
        execute_packet_code_or_test_work(_packet("pkt-dir"), repo, _Hooks(), {"authorized_mode": "LOCAL"})
    except ValueError as exc:
        assert "symlink" in str(exc).lower(), exc
    names = sorted(path.relative_to(outside).as_posix() for path in outside.rglob("*"))
    assert names == [], names


def test_evidence_does_not_follow_a_symlinked_file(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("keep", encoding="utf-8")
    repo = tmp_path / "repo"
    evidence_dir = repo / "events" / "evidence"
    evidence_dir.mkdir(parents=True)
    link = evidence_dir / "pkt-file_evidence.json"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Creating symlinks on Windows requires developer mode or administrator privilege")
        raise
    try:
        execute_packet_code_or_test_work(_packet("pkt-file"), repo, _Hooks(), {"authorized_mode": "LOCAL"})
    except ValueError as exc:
        assert "symlink" in str(exc).lower(), exc
    assert outside.read_text(encoding="utf-8") == "keep"


def test_contract_check_does_not_read_a_symlinked_source(tmp_path):
    repo = tmp_path / "repo"
    (repo / "events" / "evidence").mkdir(parents=True)
    (repo / "real.py").write_text("REAL = 1\n", encoding="utf-8")
    try:
        (repo / "link.py").symlink_to(repo / "real.py")
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Creating symlinks on Windows requires developer mode or administrator privilege")
        raise
    packet = WorkPacket(
        id="pkt-src",
        owner_id="local",
        target_sha="abc",
        state=PacketState.CURRENT,
        payload={"task_type": "code_contract_check", "allowed_scope": ["link.py"]},
    )
    try:
        result = execute_packet_code_or_test_work(packet, repo, _Hooks(), {"authorized_mode": "LOCAL"})
    except ValueError as exc:
        assert "symlink" in str(exc).lower(), exc
    else:
        raise AssertionError(result.get("verdict"))
    real = WorkPacket(
        id="pkt-real",
        owner_id="local",
        target_sha="abc",
        state=PacketState.CURRENT,
        payload={"task_type": "code_contract_check", "allowed_scope": ["real.py"]},
    )
    checked = execute_packet_code_or_test_work(real, repo, _Hooks(), {"authorized_mode": "LOCAL"})
    assert checked["verdict"] == "PASS"


def _verify_packet(packet_id, target):
    return WorkPacket(
        id=packet_id,
        owner_id="local",
        target_sha="abc",
        state=PacketState.CURRENT,
        payload={"task_type": "verify_file", "target_file": target, "allowed_scope": ["."]},
    )


def test_verify_file_does_not_read_a_symlink(tmp_path):
    repo = tmp_path / "repo"
    (repo / "events" / "evidence").mkdir(parents=True)
    (repo / "real.txt").write_text("REAL-BODY", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("SECRET", encoding="utf-8")
    try:
        (repo / "link.txt").symlink_to(repo / "real.txt")
        (repo / "out.txt").symlink_to(outside)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Creating symlinks on Windows requires developer mode or administrator privilege")
        raise
    seen = []
    for name, target in (("in", "link.txt"), ("out", "out.txt"), ("real", "real.txt")):
        packet = _verify_packet(f"pkt-{name}", target)
        try:
            result = execute_packet_code_or_test_work(packet, repo, _Hooks(), {"authorized_mode": "LOCAL"})
        except ValueError as exc:
            seen.append((name, "raised", str(exc)))
        else:
            evidence = json.loads((repo / "events" / "evidence" / f"{packet.id}_evidence.json").read_text())
            seen.append((name, result["verdict"], evidence.get("file_path"), evidence.get("file_sha256")))
    assert (
        seen[0][1] == "raised" and "symlink" in seen[0][2].lower()
        and seen[1][1] == "raised" and "symlink" in seen[1][2].lower()
        and seen[2][1] == "PASS"
        and seen[2][2] == "real.txt"
    ), seen
    assert outside.read_text(encoding="utf-8") == "SECRET"

