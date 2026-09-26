import base64
import hashlib
import json
from pathlib import Path

import pytest

from scripts import github_worker_adapter as adapter
from scripts.integration_contract import validate_durable_result


def packet(**changes):
    value = {"goal_id": "goal-1", "task_id": "task-1", "attempt_id": "attempt-1", "dispatch_id": "dispatch-1",
             "worker_id": "GITHUB-HOSTED", "task_type": "deterministic_transform", "input": "canary"}
    value.update(changes)
    return value


def test_validate_task_rejects_missing_identity_and_shell():
    with pytest.raises(ValueError, match="task_id"):
        adapter.validate_task(packet(task_id=""))
    with pytest.raises(ValueError, match="unsupported"):
        adapter.validate_task(packet(task_type="shell"))


@pytest.mark.parametrize("bad_result", [[], "oops", 42, None])
def test_verify_result_rejects_nondict_result(monkeypatch, tmp_path: Path, bad_result):
    with pytest.raises(ValueError, match="must be a JSON object"):
        adapter.verify_result(packet(), bad_result, None, "99", tmp_path)


@pytest.mark.parametrize("bad_evidence", [[], "oops", 42])
def test_verify_result_rejects_nondict_evidence(monkeypatch, tmp_path: Path, bad_evidence):
    task = packet()
    result = {
        **task,
        "run_id": "99",
        "run_attempt": "1",
        "source_sha": "a" * 40,
        "result_id": "result-dispatch-1",
        "status": "SUCCESS",
        "operation": "deterministic_transform",
        "artifacts": [{"path": "courier_output_dispatch-1.json", "sha256": "x"}],
    }
    with pytest.raises(ValueError, match="must be a JSON object"):
        adapter.verify_result(task, result, bad_evidence, "99", tmp_path)


@pytest.mark.parametrize("bad_input", [None, 42, ["x"], {"x": 1}])
def test_validate_task_rejects_non_string_transform_input(bad_input):
    with pytest.raises(ValueError, match="string input"):
        adapter.validate_task(packet(input=bad_input))


def test_find_run_uses_exact_dispatch_title(monkeypatch):
    monkeypatch.setattr(adapter, "run_cmd", lambda _: (0, json.dumps([
        {"databaseId": 4, "status": "queued", "displayTitle": "Courier dispatch dispatch-1"},
        {"databaseId": 5, "status": "completed", "displayTitle": "Courier dispatch dispatch-10"},
    ]), ""))
    assert adapter.find_run("dispatch-1") == ("4", "queued")


def test_verified_completed_result_posts_and_records_run_attempt(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    evidence = {"operation": "deterministic_transform", "input_sha256": hashlib.sha256(b"canary").hexdigest()}
    posted = []
    monkeypatch.setattr(adapter, "find_run", lambda _: ("99", "completed"))
    monkeypatch.setattr(adapter, "download_result", lambda _, __, directory: (
        {**packet(), "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "SUCCESS",
         "operation": "deterministic_transform", "artifacts": [{"path": "courier_output_dispatch-1.json", "sha256": "x"}]}, evidence))
    monkeypatch.setattr(adapter, "verify_result", lambda *args: None)
    monkeypatch.setattr(adapter, "post_result", posted.append)
    assert adapter.run(str(task_file)) == 0
    assert posted[0]["run_id"] == "99"
    assert json.loads(adapter.state_path(task_file).read_text())["run_attempt"] == "1"


def test_existing_waiting_dispatch_is_reconciled_not_dispatched(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.write_state(task_file, {"dispatch_id": "dispatch-1", "status": "WAITING_FOR_WORKER"})
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "find_run", lambda _: (None, None))
    monkeypatch.setattr(adapter, "run_cmd", lambda command: pytest.fail(f"must not redispatch: {command}"))
    monkeypatch.setattr(adapter, "post_result", lambda res: None)
    assert adapter.run(str(task_file)) == 0


def test_wait_timeout_posts_failed_result_and_marks_posted(tmp_path: Path, monkeypatch):
    """Deadline expiry must post a terminal FAILED/TIMEOUT result, never exit silently."""
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    posted = []
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "find_run", lambda _: (None, None))
    monkeypatch.setattr(adapter, "run_cmd", lambda command: (0, "branch", ""))
    monkeypatch.setattr(adapter, "post_result", posted.append)
    assert adapter.run(str(task_file)) == 0
    assert len(posted) == 1
    assert posted[0]["status"] == "FAILED"
    assert posted[0]["raw_result"]["reason"] == "TIMEOUT"
    assert posted[0]["dispatch_id"] == "dispatch-1"
    assert json.loads(adapter.state_path(task_file).read_text())["status"] == "POSTED"


def test_dispatch_preserves_taskpacket_as_raw_json(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    monkeypatch.setattr(adapter, "find_run", lambda _: (None, None))
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    commands = []
    monkeypatch.setattr(adapter, "run_cmd", lambda command: (commands.append(command) or (0, "branch", "")))
    monkeypatch.setattr(adapter, "post_result", lambda res: None)
    assert adapter.run(str(task_file)) == 0
    dispatch = next(command for command in commands if command[:3] == ["gh", "workflow", "run"])
    assert "--raw-field" in dispatch
    encoded = dispatch[dispatch.index("--raw-field") + 1].removeprefix("task_payload_base64=")
    assert json.loads(base64.b64decode(encoded))["dispatch_id"] == "dispatch-1"


def test_durable_result_preserves_github_run_attempt():
    task = packet()
    result = {
        **packet(), "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1",
        "status": "SUCCESS", "artifacts": [{"path": "courier_output_dispatch-1.json", "sha256": "a" * 64}],
    }
    assert validate_durable_result(task, result)["run_attempt"] == "1"


def test_post_result_uses_courier_bearer_token(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        text = ""

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setenv("COURIER_API_KEY", "courier-test-token")
    monkeypatch.setenv("COURIER_SERVER", "http://courier.test/")
    monkeypatch.setattr(adapter.requests, "post", fake_post)

    adapter.post_result({"result_id": "result-1"})

    assert captured["url"] == "http://courier.test/tasks/result"
    assert captured["headers"]["Authorization"] == "Bearer courier-test-token"
