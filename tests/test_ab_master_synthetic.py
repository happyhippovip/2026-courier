"""Synthetic A→B on the master path. No provider, no exchange, no spend."""

import hashlib
import json

import pytest

from courier_core.controller import Controller
from courier_hub.mission_chip import run_mission_chip
from courier_runtime.lease import LeaseConflict, LeaseStore, StaleLease
from scripts.courier_mailbox import process_inbox
from scripts.resource_policy import CostGate


def test_synthetic_controller_worker_verifier_and_replay(tmp_path):
    unknown = CostGate.evaluate_spend_request("google_antigravity_plus")
    budget = CostGate.evaluate_spend_request(
        "google_antigravity_plus", estimated_cost_eur=1.0
    )
    free = CostGate.evaluate_spend_request(
        "google_antigravity_plus", estimated_cost_eur=0.0
    )
    missing_provider = CostGate.evaluate_spend_request(
        "provider-not-registered", estimated_cost_eur=0.0
    )
    assert unknown["allowed"] is False and unknown["reason"] == "UNKNOWN_COST"
    assert budget["allowed"] is False and budget["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"
    assert free["allowed"] is True and free["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"
    assert missing_provider["allowed"] is False
    assert missing_provider["reason"] == "UNAUTHORIZED_RESOURCE_TIER"

    leases = LeaseStore(str(tmp_path / "lease.db"))
    try:
        with pytest.raises(StaleLease):
            leases.check_write("repo://ab", 1, "nobody")
        held = leases.acquire("repo://ab", "worker-a", "wk-ab", ttl_s=30)
        with pytest.raises(LeaseConflict):
            leases.acquire("repo://ab", "worker-b", "wk-ab", ttl_s=30)
        assert leases.check_write("repo://ab", held.token, "worker-a").holder == "worker-a"
    finally:
        leases.close()

    clock = {"now": 1_000.0}
    expired = LeaseStore(str(tmp_path / "expired.db"), clock=lambda: clock["now"])
    try:
        old = expired.acquire("repo://ab", "worker-a", "wk-ab", ttl_s=10)
        clock["now"] = 2_000.0
        with pytest.raises(StaleLease):
            expired.check_write("repo://ab", old.token, "worker-a")
        taken = expired.acquire("repo://ab", "worker-b", "wk-next", ttl_s=10)
        assert taken.holder == "worker-b"
        assert taken.token != old.token
    finally:
        expired.close()

    home = tmp_path / "chip"
    result = run_mission_chip(home)
    blob = (home / "mission_result.txt").read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    assert result["overall_status"] == "COMPLETE"
    assert result["cost_eur"] == 0.0
    assert result["verifier_result"]["resolution"] == "verified"
    assert result["verifier_result"]["artifact_sha256"] == digest
    assert result["checks"][0]["status"] == "PASS"
    assert result["checks"][1]["status"] == "PASS"
    assert result["checks"][2]["status"] == "PASS"

    restarted = Controller(home).boot()
    try:
        view = restarted.task_view(result["task_id"])
        assert view["status"] == "COMPLETE"
        assert view["resolution"] == "verified"
        assert view["accepted_result_id"] == "res-chip-v139-01"
    finally:
        restarted.stop()

    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    task = {
        "task_id": "mission-same",
        "name": "synthetic",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n" + json.dumps(task) + "\n", encoding="utf-8")
    mail_home = tmp_path / "mail-home"
    first = process_inbox(inbox, outbox, home_path=mail_home)
    second = process_inbox(inbox, outbox, home_path=mail_home)
    assert len(first) == 1
    assert len(second) == 0
    assert first[0]["execution_result"]["cost_eur"] == 0.0
    out_lines = [line for line in outbox.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(out_lines) == 1
