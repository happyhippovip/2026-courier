import os
import json
import pytest
from pathlib import Path
from scripts.run_chief_commander import (
    ChiefDecisionContract,
    evaluate_value_gate,
    SmartResourceRouter,
    save_json_atomic,
    ChiefCommander,
)


def test_chief_decision_contract_defaults():
    contract = ChiefDecisionContract()
    assert contract.schema_version == "2.0"
    assert contract.decision == "COMPLETE"
    assert contract.chief_decision_id.startswith("dec-chief-")
    assert contract.chief_turn_id.startswith("turn-")
    assert contract.created_at != ""
    assert isinstance(contract.to_dict(), dict)

def test_chief_decision_contract_invalid_decision():
    with pytest.raises(ValueError, match="Invalid Chief decision"):
        ChiefDecisionContract(decision="FOO_BAR")

def test_evaluate_value_gate_passes():
    payload = {"data": "some new info", "verdict": "PASS"}
    result = evaluate_value_gate(payload)
    assert result["creates_new_information"] is True
    assert result["advances_production"] is True
    assert result["passed"] is True

def test_evaluate_value_gate_is_noop():
    payload = {"data": "some new info", "verdict": "PASS", "is_noop": True}
    result = evaluate_value_gate(payload)
    assert result["creates_new_information"] is False
    assert result["advances_production"] is False
    assert result["passed"] is False

def test_smart_resource_router_codex():
    target, reason, exec_class = SmartResourceRouter.classify_and_route("Perform a code review", ["test.py"])
    assert target == "codex"
    assert "code review" in reason

def test_smart_resource_router_antigravity_heavy():
    target, reason, exec_class = SmartResourceRouter.classify_and_route("Render a 3D asset", ["model.obj"])
    assert target == "antigravity"
    assert "3D" in reason or "3d" in reason.lower()

def test_smart_resource_router_default():
    target, reason, exec_class = SmartResourceRouter.classify_and_route("Do some generic task", ["file.txt"])
    assert target == "antigravity"
    assert "Default" in reason

def test_save_json_atomic(tmp_path):
    target_file = tmp_path / "atomic.json"
    data = {"key": "value"}
    save_json_atomic(target_file, data)
    assert target_file.exists()
    assert json.loads(target_file.read_text(encoding="utf-8")) == data

def test_chief_commander_presence(tmp_path):
    chief = ChiefCommander(repo_dir=tmp_path)
    # Check default
    presence = chief.get_presence()
    assert presence["presence"] == "AWAKE"

    # Set SLEEPING
    chief.set_presence("SLEEPING", session_id="s1")
    presence = chief.get_presence()
    assert presence["presence"] == "SLEEPING"
    assert presence["session_id"] == "s1"
    
    with pytest.raises(ValueError, match="Invalid presence state"):
        chief.set_presence("FOO_BAR")

def test_log_night_journal(tmp_path):
    chief = ChiefCommander(repo_dir=tmp_path)
    journal_file = chief.log_night_journal("s1", {"event": "test"})
    assert journal_file.exists()
    lines = journal_file.read_text(encoding="utf-8").strip().split("\n")
    data = json.loads(lines[0])
    assert data["event"] == "test"
    assert "timestamp" in data
    assert "chief_presence" in data

def test_evaluate_result_and_decide_needs_fix(tmp_path):
    chief = ChiefCommander(repo_dir=tmp_path)
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps({
        "payload": {"verdict": "NEEDS_FIX", "target_files": ["foo.py"]},
        "source": "codex"
    }), encoding="utf-8")
    
    decision = chief.evaluate_result_and_decide(
        task_id="t1",
        correlation_id="c1",
        workflow_id="wf1",
        result_file=result_file
    )
    assert decision.decision == "RETRY_SAFE"
    assert decision.next_task["task_id"] == "wf1-REPAIR-1"
    assert decision.next_task["target_agent"] == "codex"

def test_evaluate_result_and_decide_pass_no_next(tmp_path):
    chief = ChiefCommander(repo_dir=tmp_path)
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps({
        "payload": {"verdict": "PASS", "data": "something new"},
        "source": "antigravity"
    }), encoding="utf-8")
    
    decision = chief.evaluate_result_and_decide(
        task_id="t1",
        correlation_id="c1",
        workflow_id="wf1",
        result_file=result_file
    )
    # A model PASS is not progress without a grant, a workkey, and a known resource state.
    assert decision.decision == "PAUSE"
    assert decision.next_task is None
    reason = decision.reason.lower()
    assert "grant" in reason
    assert "workkey" in reason
    assert "resource" in reason


def test_suggestion_without_grant_workkey_or_resource_state_pauses(tmp_path):
    chief = ChiefCommander(repo_dir=tmp_path)
    assert chief.resource_intelligence is None
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps({
        "payload": {
            "verdict": "PASS",
            "confidence": 0.99,
            "data": "model suggested the next step",
        },
        "source": "antigravity",
    }), encoding="utf-8")
    decision = chief.evaluate_result_and_decide(
        task_id="t-gate",
        correlation_id="c-gate",
        workflow_id="wf-gate",
        result_file=result_file,
        workflow_plan=[
            {
                "task_id": "wf-gate-STEP-1",
                "instruction": "completed step",
                "target_agent": "antigravity",
            },
            {
                "task_id": "wf-gate-STEP-2",
                "instruction": "continue from the model suggestion",
                "target_agent": "antigravity",
            },
        ],
        round_index=0,
    )
    assert decision.decision == "PAUSE"
    assert decision.next_task is None
    reason = decision.reason.lower()
    assert "grant" in reason
    assert "workkey" in reason
    assert "resource" in reason
