"""Regression: NEEDS_FIX repair dispatch must not raise NameError.

AutonomousLevel6Loop.evaluate_chief_decision builds a scoped repair task
when QA verification fails (action QUEUE_SCOPED_REPAIR_TASK). The repair
record referenced an undefined name (res_data) for target_agent, so every
failed-QA decision crashed instead of dispatching the repair — the exact
path that must work when quality gates fail.

Calls the unbound method with a stub self (only repo_dir is used on this
path); isolated tmp dirs; no network, no provider.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from scripts.run_autonomous_loop import AutonomousLevel6Loop


def write_result(path, verdict="NEEDS_FIX", source="antigravity"):
    payload = {"verdict": verdict, "target_file": ["some/file.py"]}
    data = {"payload": payload, "source": source}
    Path(path).write_text(json.dumps(data), encoding="utf-8")


class StubSteward:
    def __init__(self):
        self.events = []

    def refresh_snapshot_after_event(self, event, task_id):
        self.events.append((event, task_id))


def decide(repo_dir, result_file, task_id="t1"):
    self_stub = SimpleNamespace(
        repo_dir=Path(repo_dir), steward=StubSteward())
    return AutonomousLevel6Loop.evaluate_chief_decision(
        self_stub,
        task_id=task_id,
        correlation_id="corr-1",
        result_file=Path(result_file),
        workflow_id="wf-1",
        round_index=0,
    )


def test_needs_fix_dispatches_scoped_repair(tmp_path):
    result_file = tmp_path / "result.json"
    write_result(result_file)
    decision = decide(tmp_path, result_file)
    assert decision["verdict"] == "NEEDS_FIX"
    assert decision["action"] == "QUEUE_SCOPED_REPAIR_TASK"
    nxt = decision["next_task"]
    assert nxt["task_id"] == "repair-t1"
    assert nxt["target_agent"] == "antigravity"
    assert nxt["allowed_scope"] == ["some/file.py"]
    persisted = json.loads(
        (tmp_path / "events/chief-decisions/t1-chief-decision.json")
        .read_text(encoding="utf-8"))
    assert persisted["action"] == "QUEUE_SCOPED_REPAIR_TASK"


def test_needs_fix_honors_result_source(tmp_path):
    result_file = tmp_path / "result.json"
    write_result(result_file, source="codex")
    decision = decide(tmp_path, result_file)
    assert decision["next_task"]["target_agent"] == "codex"


def test_needs_fix_defaults_source_to_antigravity(tmp_path):
    result_file = tmp_path / "result.json"
    Path(result_file).write_text(
        json.dumps({"payload": {"verdict": "NEEDS_FIX"}}),
        encoding="utf-8")
    decision = decide(tmp_path, result_file)
    assert decision["next_task"]["target_agent"] == "antigravity"
