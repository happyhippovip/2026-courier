import json
from concurrent.futures import ThreadPoolExecutor
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


def test_result_write_is_idempotent_but_never_overwrites_conflict(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge, "PROCESSED_DIR", tmp_path)
    hooks = bridge.CodexHookRunner(_StateTracker())

    result_file = hooks.on_task_completion("task-1", "corr-1", "msg-1", {"verdict": "PASS"})
    original = result_file.read_bytes()
    hooks.on_task_completion("task-1", "corr-1", "msg-1", {"verdict": "PASS"})
    assert result_file.read_bytes() == original

    with pytest.raises(RuntimeError, match="Conflicting result"):
        hooks.on_task_completion("task-1", "corr-1", "msg-1", {"verdict": "FAIL"})
    assert result_file.read_bytes() == original


def test_dedupe_rejects_result_from_different_dispatch_identity(monkeypatch, tmp_path):
    processed = tmp_path / "processed"
    monkeypatch.setattr(bridge, "PROCESSED_DIR", processed)
    processed.mkdir()
    payload = {"verdict": "PASS"}
    (processed / "task-1-result.json").write_text(
        json.dumps(
            {
                "task_id": "task-1",
                "correlation_id": "corr-old",
                "parent_id": "msg-old",
                "source": "codex",
                "destination": "courier",
                "type": "RESULT",
                "status": "COMPLETED",
                "payload": payload,
                "payload_hash": bridge.payload_hash(payload),
            }
        ),
        encoding="utf-8",
    )
    job_path = tmp_path / "job.json"
    job_path.write_text(
        json.dumps(
            {
                "task_id": "task-1",
                "correlation_id": "corr-new",
                "source_command_message_id": "msg-new",
                "allowed_scope": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="identity conflicts"):
        bridge.execute_codex_task(job_path, _Hooks())


def test_concurrent_conflicting_results_have_exactly_one_immutable_winner(tmp_path):
    result_file = tmp_path / "task-1-result.json"

    def write(verdict):
        payload = {"verdict": verdict}
        result = {
            "task_id": "task-1",
            "correlation_id": "corr-1",
            "parent_id": "msg-1",
            "source": "codex",
            "destination": "courier",
            "type": "RESULT",
            "status": "COMPLETED",
            "payload": payload,
            "payload_hash": bridge.payload_hash(payload),
        }
        try:
            bridge.persist_result_once(result_file, result)
            return "accepted"
        except RuntimeError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(write, ["PASS", "FAIL"] * 8))

    persisted = json.loads(result_file.read_text(encoding="utf-8"))
    assert persisted["payload_hash"] == bridge.payload_hash(persisted["payload"])
    assert "accepted" in outcomes
    assert "conflict" in outcomes


def test_atomic_json_save_preserves_previous_state_when_replace_fails(monkeypatch, tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text('{"state": "old"}\n', encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(bridge.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        bridge.save_json(state_file, {"state": "new"})

    assert json.loads(state_file.read_text(encoding="utf-8")) == {"state": "old"}
    assert list(tmp_path.glob("*.tmp")) == []
