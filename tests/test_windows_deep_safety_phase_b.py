"""Phase B Windows deep safety tests (GW-407 to GW-414).

Verifies at-most-once execution, crash recovery, claim safety, process nonce binding,
and fail-closed authority lease mechanics on Windows.
"""
import json
import os
import time
from pathlib import Path

import pytest

from scripts.verified_continuation import VerifiedContinuation
from tests.test_windows_worker_contract import (
    Bridge,
    StopLoop,
    central,
    go,
    load_daemon,
    load_daemon_again,
    state_file,
)


# GW-407: Stale Owner & Invalid / Tampered Process-Nonce
def test_gw407_stale_owner_and_tampered_process_nonce(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    ledger = tmp_path / "ledger"
    engine = VerifiedContinuation(root_dir=root, ledger_dir=ledger)

    # 1. Tampered / invalid holder_nonce cannot be renewed by anyone
    claim_path = engine.claims_dir / "WK-407.claim"
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    claim_path.write_text(
        json.dumps({
            "workkey": "WK-407",
            "owner": "google-antigravity",
            "pid": os.getpid(),
            "holder_nonce": None,  # Corrupted/invalid nonce
            "created_at_ts": time.time(),
            "ttl_s": 3600,
        }),
        encoding="utf-8",
    )
    # Even the same PID cannot renew without matching valid nonce
    assert engine.claim("WK-407", owner="google-antigravity") is False

    # 2. Stale owner after expiry cannot take over without human reclaim
    claim_path.write_text(
        json.dumps({
            "workkey": "WK-407",
            "owner": "worker-stale",
            "pid": 999999,
            "holder_nonce": "stale-nonce-1234",
            "created_at_ts": time.time() - 7200,
            "ttl_s": 60,
        }),
        encoding="utf-8",
    )
    assert engine.claim("WK-407", owner="worker-new") is False

    # 3. Explicit human reclaim frees it for worker-new
    engine.reclaim("WK-407", actor="dennis", reason="stale worker dead, verified stopped")
    assert engine.claim("WK-407", owner="worker-new") is True
    assert engine.is_claimed("WK-407")["owner"] == "worker-new"


# GW-408: Crash between CLAIMED and STARTED simulated
def test_gw408_crash_between_claimed_and_started_simulated(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()["task"]
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)

    # Simulate crash right after claim was written to disk, before run_task started
    state_file(daemon).write_text(json.dumps(dict(claimed, worker_phase="CLAIMED")))

    effect = daemon.APP_DATA_DIR / "effect.txt"
    bridge = Bridge(http, headers, max_calls=6)
    go(daemon, monkeypatch, bridge, executions, effect=effect, tmp_path=tmp_path)

    # Worker resumed, ran task exactly once, and delivered result
    assert executions == ["task-1"]
    task = srv.load_state()["tasks"]["task-1"]
    assert task["status"] == "RESULT_RECEIVED"
    assert not state_file(daemon).exists()


# GW-409: Crash after STARTED prevents duplicate execution
def test_gw409_crash_after_started_prevents_duplicate_execution(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()["task"]
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)

    # Simulate crash mid-execution (phase was persisted as STARTED)
    state_file(daemon).write_text(json.dumps(dict(claimed, worker_phase="STARTED")))

    bridge = Bridge(http, headers, max_calls=5)
    go(daemon, monkeypatch, bridge, executions, tmp_path=tmp_path)

    # Worker MUST NOT re-execute interrupted task; it releases to server recovery
    assert executions == []
    state = srv.load_state()
    assert state["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
    assert state["workers"]["WIN-01"]["current_task"] is None
    assert not state_file(daemon).exists()


# GW-410: RESULT_READY only redelivers, never recomputes
def test_gw410_result_ready_only_redelivers_never_recomputes(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch, artifacts=("effect.txt",))
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()["task"]
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)

    # Prepare pre-computed result with proper artifact
    (daemon.APP_DATA_DIR / "effect.txt").write_bytes(b"precomputed-bytes\n")
    res_payload = daemon.build_result_payload(
        claimed,
        {"status": "SUCCESS", "run_id": "win-pre", "stdout": "", "stderr": ""},
        {"WORKER_ID": "WIN-01"},
    )
    state_file(daemon).write_text(
        json.dumps(dict(claimed, worker_phase="RESULT_READY", result_payload=res_payload))
    )

    # First restart: posts precomputed result without running task
    daemon_n = load_daemon_again(tmp_path, monkeypatch)
    bridge = Bridge(http, headers, max_calls=4)
    go(daemon_n, monkeypatch, bridge, executions, tmp_path=tmp_path)
    posted = bridge.posted("/tasks/result")
    assert len(posted) == 1
    assert posted[0] == res_payload

    # Exactly 0 executions of task logic
    assert executions == []
    assert srv.load_state()["tasks"]["task-1"]["status"] == "RESULT_RECEIVED"


# GW-411: RELEASE_PENDING and Double-FINAL prevention
def test_gw411_release_pending_and_double_final_rejection(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()["task"]
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)

    # State was persisted as RELEASE_PENDING after a 4xx rejection
    state_file(daemon).write_text(json.dumps(dict(claimed, worker_phase="RELEASE_PENDING")))

    bridge = Bridge(http, headers, max_calls=5)
    go(daemon, monkeypatch, bridge, executions, tmp_path=tmp_path)

    assert executions == []
    state = srv.load_state()
    assert state["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"
    assert not state_file(daemon).exists()

    # Double-FINAL prevention: posting result for a task that is already HUMAN_REQUIRED returns 409 Conflict
    req_data = json.dumps({"task_id": "task-1", "worker_id": "WIN-01", "status": "SUCCESS", "artifacts": []})
    resp = http.post("/tasks/result", headers=headers, data=req_data)
    assert resp.status_code == 409


# GW-412: Corrupted or missing LeaseStore mid-loop fails closed
def test_gw412_corrupted_leasestore_mid_loop_fails_closed(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    lock_file = daemon.acquire_lock("WIN-01")
    assert lock_file is not None

    # Corrupt the authority db while loop is running
    authority_db = daemon.STATE_DIR / "authority.db"
    authority_db.write_bytes(b"corrupt header junk")

    # Calling _require_canonical_lease() must fail closed
    with pytest.raises(daemon.CanonicalLeaseLost):
        daemon._require_canonical_lease()

    daemon.release_lock(lock_file)


# GW-413: Two Homes with expired claim and still-living original process
def test_gw413_two_homes_expired_claim_living_original_process(tmp_path):
    root1 = tmp_path / "home1" / "repo"
    root1.mkdir(parents=True)
    ledger1 = tmp_path / "home1" / "ledger"
    engine1 = VerifiedContinuation(root_dir=root1, ledger_dir=ledger1)

    root2 = tmp_path / "home2" / "repo"
    root2.mkdir(parents=True)
    ledger2 = tmp_path / "home2" / "ledger"
    engine2 = VerifiedContinuation(root_dir=root2, ledger_dir=ledger2)

    # Engine 1 claims WK-413 with PID of current living process
    assert engine1.claim("WK-413", owner="worker-living", ttl_s=1) is True

    # Simulate shared claims filesystem or sync to Home 2
    claim_data = json.loads((engine1.claims_dir / "WK-413.claim").read_text())
    claim_data["created_at_ts"] = time.time() - 3600  # Expired
    engine2.claims_dir.mkdir(parents=True, exist_ok=True)
    (engine2.claims_dir / "WK-413.claim").write_text(json.dumps(claim_data))

    # Engine 2 cannot take it over even though TTL expired, because PID is still alive and no reclaim
    assert engine2.claim("WK-413", owner="worker-contender") is False

    # Only explicit reclaim allows Engine 2 to take it over
    engine2.reclaim("WK-413", actor="admin", reason="home1 process abandoned work")
    assert engine2.claim("WK-413", owner="worker-contender") is True
    assert engine2.is_claimed("WK-413")["owner"] == "worker-contender"


# GW-414: Dead-Letter and Replay with identical workkey
def test_gw414_dead_letter_and_replay_with_identical_workkey(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()["task"]
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)

    # Task transitions to HUMAN_REQUIRED (dead-letter)
    state_file(daemon).write_text(json.dumps(dict(claimed, worker_phase="RELEASE_PENDING")))
    go(daemon, monkeypatch, Bridge(http, headers, max_calls=5), executions, tmp_path=tmp_path)
    assert srv.load_state()["tasks"]["task-1"]["status"] == "HUMAN_REQUIRED"

    # Replayed claim request for WIN-01 returns no task (quarantined)
    res = http.post("/tasks/claim", headers=headers, json={"worker_id": "WIN-01"}).get_json()
    assert res.get("task") is None
