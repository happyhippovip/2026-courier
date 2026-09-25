"""Chief decision artifacts must stay inside events/chief-decisions.

task_id (evaluate path) and alert message_id (SNITCH path) flow into
filenames. A worker- or alert-controlled "../" must fail closed instead
of writing outside the decisions directory.
"""
from types import SimpleNamespace

import pytest

from scripts.run_chief_commander import ChiefCommander


def alert(message_id="../../evil"):
    return {
        "message_id": message_id,
        "workflow_id": "wf-1",
        "correlation_id": "corr-1",
        "classification": "STALLED",
        "reason": "test stall",
        "agent_id": "agent-snitch",
    }


def test_review_runtime_alert_rejects_path_unsafe_message_id(tmp_path):
    mgr = ChiefCommander(tmp_path)
    with pytest.raises(ValueError, match="path-safe"):
        mgr.review_runtime_alert(alert())
    assert list(tmp_path.rglob("*evil*")) == []
    assert list(tmp_path.parent.glob("*evil*")) == []


def test_persist_decision_rejects_path_unsafe_task_id(tmp_path):
    mgr = ChiefCommander(tmp_path)
    decision = SimpleNamespace(to_dict=lambda: {"verdict": "OK"})
    with pytest.raises(ValueError, match="path-safe"):
        mgr._persist_decision("../../evil", decision)
    assert list(tmp_path.rglob("*evil*")) == []


def test_safe_ids_still_persist(tmp_path):
    mgr = ChiefCommander(tmp_path)
    out = mgr.review_runtime_alert(alert("msg-1"))
    assert out["verdict"] == "RUNTIME_ALERT_REVIEWED"
    assert (tmp_path / "events" / "chief-decisions" / "msg-1-chief-decision.json").is_file()
