import pytest
import datetime
import sys
from pathlib import Path

# Add scripts directory to path to import agent_handoff_ledger
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import agent_handoff_ledger as ahl

import copy
from tests.test_agent_handoff_ledger import record as _raw_record, guard as _raw_guard


def base_record() -> dict:
    rec = _raw_record()
    rec["GOAL"] = "goal-dlq02"
    rec["PROVEN_EDGES"] = ["issue state", "runtime artifact"]
    rec["UNPROVEN_EDGES"] = []
    return rec


def base_guard() -> dict:
    return _raw_guard()


def _mock_attestation(monkeypatch, g):
    monkeypatch.setattr(
        ahl,
        "_verify_attestation",
        lambda url: {
            "verdict": "PASS",
            "producer_principal": "stale-producer",
            "verifier_principal": "stale-verifier",
            "result_sha256": "sha256-dlq02",
            "goal_id": "goal-dlq02",
            "binding": {
                "sha": g["binding"]["current_sha"],
                "runtime": g["binding"]["runtime_identity"],
            },
        },
    )


def test_dlq02_stale_evidence_rejected(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    rec = base_record()
    g0 = base_guard()
    _mock_attestation(monkeypatch, g0)
    ahl.initialize(path, rec, g0, 5.0)

    g1 = base_guard()
    g1["evidence"].append({
        "source_url": "https://github.com/example/project/actions/runs/stale-1",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2020-01-01T00:00:00Z",  # Stale
        "evidence_sha": g1["binding"]["current_sha"],
        "runtime_binding": g1["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "ancient artifact",
        "producer_id": "stale-producer",
        "verifier_id": "stale-verifier",
        "result_sha256": "sha256-dlq02",
    })

    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"

    g2 = copy.deepcopy(b1["acceptance_guard"])
    g2["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS",
        "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/stale-1"],
    }
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0, g2)
    assert b2["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    assert b2["record"]["CLEAN_IDLE"] == "NO"


def test_dlq02_fresh_evidence_accepted(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    rec = base_record()
    g0 = base_guard()
    _mock_attestation(monkeypatch, g0)
    ahl.initialize(path, rec, g0, 5.0)

    g1 = base_guard()
    g1["evidence"].append({
        "source_url": "https://github.com/example/project/actions/runs/stale-1",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),  # Fresh
        "evidence_sha": g1["binding"]["current_sha"],
        "runtime_binding": g1["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "fresh artifact",
        "producer_id": "stale-producer",
        "verifier_id": "stale-verifier",
        "result_sha256": "sha256-dlq02",
    })

    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"

    g2 = copy.deepcopy(b1["acceptance_guard"])
    g2["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS",
        "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/stale-1"],
    }
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0, g2)
    assert b2["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"
    assert b2["record"]["CLEAN_IDLE"] == "YES"
