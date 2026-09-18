import json
from pathlib import Path

import pytest

from scripts import run_codex_bridge as bridge


class _Hooks:
    def on_task_failure(self, *args, **kwargs):
        raise AssertionError("invalid identity reached a filesystem-producing hook")


class _StateTracker:
    def update_state(self, **kwargs):
        return kwargs


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_id", "../../outside"),
        ("task_id", "task/child"),
        ("correlation_id", "corr/child"),
        ("source_command_message_id", "../parent"),
    ],
)
def test_bridge_rejects_unsafe_identity_before_result_path(tmp_path, field, value):
    job = {
        "task_id": "task-safe",
        "correlation_id": "corr-safe",
        "source_command_message_id": "msg-safe",
        "allowed_scope": [],
    }
    job[field] = value
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")

    with pytest.raises(ValueError, match=f"Invalid {field}"):
        bridge.execute_codex_task(job_path, _Hooks())


def test_real_cli_rejects_unsafe_task_id_before_temp_path(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "CODEX_CLI_PATH", Path("/bin/true"))
    monkeypatch.setattr(bridge, "COURIER_DIR", tmp_path)

    with pytest.raises(ValueError, match="Invalid task_id"):
        bridge.execute_real_codex_cli("inspect", [], "../../outside")

    assert not (tmp_path.parent / "outside_codex_out.txt").exists()


@pytest.mark.parametrize("method", ["on_task_completion", "on_task_failure", "on_task_stop"])
def test_hooks_reject_unsafe_task_id_when_called_directly(method):
    hooks = bridge.CodexHookRunner(_StateTracker())
    call = getattr(hooks, method)

    with pytest.raises(ValueError, match="Invalid task_id"):
        if method == "on_task_completion":
            call("../outside", "corr-safe", None, {"verdict": "PASS"})
        elif method == "on_task_failure":
            call("../outside", "corr-safe", None, "failure")
        else:
            call("../outside")


def test_review_router_rejects_unsafe_task_id_before_decision_path(tmp_path):
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps({"payload": {"verdict": "PASS"}}), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid task_id"):
        bridge.run_chief_review_router("../outside", result_file)
