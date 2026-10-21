"""Comprehensive Contract Tests for CP-11 / CQ-11:
Recovery: Startup-Reihenfolge zur Verhinderung einer zweiten Ausführung bereits gestarteter Arbeit.

Sequence:
Laden -> Prozesse/Leases/Results abgleichen -> READY berechnen -> Dispatch.

Acceptance Criteria:
1. Vor Reconciliation kein neuer Konflikt-Dispatch.
2. Bestätigte Ergebnisse bleiben erhalten.
3. Fehlende Runtime-Evidenz wird nicht erfunden (Quarantäne statt blindem Re-dispatch).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
import pytest

from courier_core.startup_recovery import (
    StartupRecoveryEngine,
    StartupPhase,
    RecoveryAction,
    ConflictDispatchBlockedError,
)
from server import app as server_app


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


# =========================================================================
# Part 1: Core Engine 4-Phase Sequence Tests
# =========================================================================

def test_startup_recovery_four_phase_progression():
    """Beweist: Die Recovery durchläuft strikt die 4 Phasen:

    LOADING -> RECONCILING -> COMPUTING_READY -> DISPATCH_READY.
    """
    engine = StartupRecoveryEngine()
    assert engine.phase == StartupPhase.UNINITIALIZED

    # Dispatch vor Reconciliation ist verboten!
    with pytest.raises(ConflictDispatchBlockedError, match="startup reconciliation must complete first"):
        engine.assert_can_dispatch()

    raw_state = {
        "goals": {
            "g1": {
                "goal_id": "g1",
                "status": "ACTIVE",
                "workflow_plan": [
                    {"task_id": "t1", "status": "QUEUED", "effect_class": "idempotent"}
                ],
            }
        },
        "tasks": {
            "t1": {"task_id": "t1", "status": "QUEUED", "goal_id": "g1", "effect_class": "idempotent"}
        },
        "workers": {"w1": {"worker_id": "w1", "available": True}},
    }

    state_after, report = engine.execute_recovery(raw_state)

    assert report.phase == StartupPhase.DISPATCH_READY
    assert report.dispatch_gate_open is True
    assert "t1" in report.ready_task_ids
    # Jetzt ist der Dispatch-Gate geöffnet
    engine.assert_can_dispatch()


def test_confirmed_results_are_preserved_across_restart():
    """Beweist: Bestätigte Ergebnisse bleiben erhalten.

    Ein Task, der vor dem Absturz bereits ein Ergebnis hatte, wird zu RESULT_RECEIVED
    wiederhergestellt und NICHT erneut ausgeführt.
    """
    engine = StartupRecoveryEngine()

    raw_state = {
        "goals": {
            "g1": {
                "goal_id": "g1",
                "status": "ACTIVE",
                "workflow_plan": [
                    {"task_id": "t-done", "status": "DISPATCHED", "worker_id": "w-dead"}
                ],
            }
        },
        "tasks": {
            "t-done": {
                "task_id": "t-done",
                "goal_id": "g1",
                "status": "DISPATCHED",
                "worker_id": "w-dead",
                "result": {"status": "SUCCESS", "artifacts": ["out.txt"], "dispatch_id": "dsp-1"},
            }
        },
        "workers": {"w-dead": {"worker_id": "w-dead", "available": True}},
    }

    state_after, report = engine.execute_recovery(raw_state)

    # KERNERGEBNIS:
    t = state_after["tasks"]["t-done"]
    assert t["status"] == "RESULT_RECEIVED"
    assert t["result"]["status"] == "SUCCESS"
    assert len(report.reconciled_tasks) == 1
    assert report.reconciled_tasks[0].action == RecoveryAction.PRESERVED_CONFIRMED_RESULT


def test_missing_runtime_evidence_not_invented_quarantines_unknown_effect():
    """Beweist: Fehlende Runtime-Evidenz wird nicht erfunden.

    Ein nicht-idempotenter Task in DISPATCHED ohne Resultat wird nach einem Absturz
    quarantäniert (HUMAN_REQUIRED), um einen doppelten externen Effekt zu verhindern.
    """
    engine = StartupRecoveryEngine()

    raw_state = {
        "goals": {
            "g-finance": {
                "goal_id": "g-finance",
                "status": "ACTIVE",
                "workflow_plan": [
                    {
                        "task_id": "t-payment",
                        "status": "DISPATCHED",
                        "worker_id": "w-crashed",
                        "effect_class": "non_idempotent",
                    }
                ],
            }
        },
        "tasks": {
            "t-payment": {
                "task_id": "t-payment",
                "goal_id": "g-finance",
                "status": "DISPATCHED",
                "worker_id": "w-crashed",
                "effect_class": "non_idempotent",
            }
        },
        "workers": {"w-crashed": {"worker_id": "w-crashed", "available": True}},
    }

    state_after, report = engine.execute_recovery(raw_state)

    # KERNERGEBNISSE:
    t = state_after["tasks"]["t-payment"]
    assert t["status"] == "HUMAN_REQUIRED"
    assert t["recovery_reason"] == "STALE_WORKER_EFFECT_AMBIGUOUS"
    assert "t-payment" in report.quarantined_task_ids
    assert "t-payment" not in report.ready_task_ids
    assert state_after["goals"]["g-finance"]["status"] == "BLOCKED"


def test_idempotent_task_cleared_safely_for_retry():
    """Beweist: Idempotente Aufgaben ohne Schadensrisiko werden sicher wieder in die Queue eingestellt."""
    engine = StartupRecoveryEngine()

    raw_state = {
        "goals": {
            "g1": {
                "goal_id": "g1",
                "status": "ACTIVE",
                "workflow_plan": [
                    {
                        "task_id": "t-read",
                        "status": "DISPATCHED",
                        "worker_id": "w-crashed",
                        "effect_class": "idempotent",
                    }
                ],
            }
        },
        "tasks": {
            "t-read": {
                "task_id": "t-read",
                "goal_id": "g1",
                "status": "DISPATCHED",
                "worker_id": "w-crashed",
                "effect_class": "idempotent",
            }
        },
        "workers": {"w-crashed": {"worker_id": "w-crashed", "available": True}},
    }

    state_after, report = engine.execute_recovery(raw_state)

    t = state_after["tasks"]["t-read"]
    assert t["status"] == "QUEUED"
    assert t["worker_id"] is None
    assert "t-read" in report.ready_task_ids


# =========================================================================
# Part 2: HTTP Integration with server/app.py
# =========================================================================

def test_server_claim_triggers_startup_reconciliation_preventing_conflict_dispatch(tmp_path, monkeypatch):
    """Beweist: Ein neu gestarteter Server führt vor dem ersten Dispatch

    automatisch die Startup-Reconciliation durch. Kein Konflikt-Dispatch!
    """
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")

    # Vorabzustand: Ein nicht-idempotenter Task war während des Absturzes DISPATCHED
    initial_state = {
        "goals": {
            "g-crash": {
                "goal_id": "g-crash",
                "status": "ACTIVE",
                "workflow_plan": [
                    {
                        "task_id": "t-in-flight",
                        "status": "DISPATCHED",
                        "worker_id": "w-old",
                        "effect_class": "non_idempotent",
                        "target_capability": "windows",
                    }
                ],
            }
        },
        "tasks": {
            "t-in-flight": {
                "task_id": "t-in-flight",
                "goal_id": "g-crash",
                "status": "DISPATCHED",
                "worker_id": "w-old",
                "effect_class": "non_idempotent",
                "target_capability": "windows",
            }
        },
        "workers": {
            "w-fresh": {"worker_id": "w-fresh", "available": True, "capabilities": ["windows"], "last_seen": time.time()}
        },
    }
    state_file.write_text(json.dumps(initial_state), encoding="utf-8")

    client = server_app.app.test_client()

    # Ein neuer Worker versucht die Aufgabe abzugreifen:
    claim_resp = client.post("/tasks/claim", headers=auth(), json={"worker_id": "w-fresh"})
    assert claim_resp.status_code == 200
    # BEWEIS: Task darf NICHT zugewiesen werden!
    assert claim_resp.get_json()["task"] is None

    # Überprüfe den Server-State nach der automatischen Startup-Reconciliation:
    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after["_startup_reconciled"] is True
    assert state_after["tasks"]["t-in-flight"]["status"] == "HUMAN_REQUIRED"
    assert state_after["tasks"]["t-in-flight"]["recovery_reason"] == "STALE_WORKER_EFFECT_AMBIGUOUS"
    assert state_after["goals"]["g-crash"]["status"] == "BLOCKED"


def test_server_explicit_startup_reconcile_endpoint(tmp_path, monkeypatch):
    """Beweist: Der Endpoint /recovery/startup_reconcile kann explizit aufgerufen werden

    und liefert den vollständigen Reconcile-Report.
    """
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")

    initial_state = {
        "goals": {
            "g-demo": {
                "goal_id": "g-demo",
                "status": "ACTIVE",
                "workflow_plan": [
                    {"task_id": "t-sub", "status": "QUEUED", "effect_class": "idempotent"}
                ],
            }
        },
        "tasks": {
            "t-sub": {"task_id": "t-sub", "goal_id": "g-demo", "status": "QUEUED", "effect_class": "idempotent"}
        },
        "workers": {},
    }
    state_file.write_text(json.dumps(initial_state), encoding="utf-8")

    client = server_app.app.test_client()
    rec_res = client.post("/recovery/startup_reconcile", headers=auth())
    assert rec_res.status_code == 200
    rep = rec_res.get_json()

    assert rep["phase"] == "DISPATCH_READY"
    assert rep["dispatch_gate_open"] is True
    assert "t-sub" in rep["ready_task_ids"]
