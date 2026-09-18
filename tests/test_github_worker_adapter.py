import base64
import hashlib
import json
from pathlib import Path

import pytest

from scripts import github_worker_adapter as adapter
from scripts.integration_contract import validate_durable_result


def packet(**changes):
    value = {"goal_id": "goal-1", "task_id": "task-1", "attempt_id": "attempt-1", "dispatch_id": "dispatch-1",
             "execution_ref": "exec-1", "worker_id": "GITHUB-HOSTED", "task_type": "deterministic_transform", "input": "canary"}
    value.update(changes)
    return value


def test_validate_task_rejects_missing_identity_and_shell():
    with pytest.raises(ValueError, match="task_id"):
        adapter.validate_task(packet(task_id=""))
    with pytest.raises(ValueError, match="unsupported"):
        adapter.validate_task(packet(task_type="shell"))
    with pytest.raises(ValueError, match="execution_ref"):
        adapter.validate_task(packet(execution_ref=""))


def test_verify_result_rejects_wrong_execution_reference(tmp_path: Path):
    task = packet()
    evidence_file = tmp_path / "courier_output_dispatch-1.json"
    evidence_file.write_text("{}", encoding="utf-8")
    result = {
        **task,
        "execution_ref": "wrong-execution",
        "run_id": "99",
        "run_attempt": "1",
        "result_id": "result-dispatch-1",
        "status": "SUCCESS",
        "operation": "deterministic_transform",
        "artifacts": [
            {
                "path": evidence_file.name,
                "sha256": hashlib.sha256(evidence_file.read_bytes()).hexdigest(),
            }
        ],
    }

    with pytest.raises(ValueError, match="identity does not match"):
        adapter.verify_result(
            task,
            result,
            {
                "operation": "deterministic_transform",
                "input_sha256": hashlib.sha256(b"canary").hexdigest(),
            },
            "99",
            tmp_path,
        )


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
        {**packet(), "execution_ref": "ref", "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "SUCCESS",
         "operation": "deterministic_transform", "artifacts": [{"path": "courier_output_dispatch-1.json", "sha256": "x"}]}, evidence))
    monkeypatch.setattr(adapter, "verify_result", lambda *args: None)
    monkeypatch.setattr(adapter, "post_result", posted.append)
    assert adapter.run(str(task_file)) == 0
    assert posted[0]["run_id"] == "99"
    state = json.loads(adapter.state_path(task_file).read_text())
    assert state["run_attempt"] == "1"
    assert state["task_identity_sha256"] == adapter.task_identity_sha256(packet())
    assert state["task_packet_sha256"] == adapter.task_packet_sha256(packet())


def test_existing_waiting_dispatch_is_reconciled_not_dispatched(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.write_state(task_file, {"dispatch_id": "dispatch-1", "status": "WAITING_FOR_WORKER"})
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "find_run", lambda _: (None, None))
    monkeypatch.setattr(adapter, "run_cmd", lambda command: pytest.fail(f"must not redispatch: {command}"))
    assert adapter.run(str(task_file)) == 0


def test_posted_dispatch_is_terminal_and_never_replayed(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task = packet()
    task_file.write_text(json.dumps(task), encoding="utf-8")
    adapter.write_state(
        task_file,
        {
            "dispatch_id": "dispatch-1",
            "task_identity_sha256": adapter.task_identity_sha256(task),
            "task_packet_sha256": adapter.task_packet_sha256(task),
            "run_id": "99",
            "run_attempt": "1",
            "result_id": "result-dispatch-1",
            "status": "POSTED",
        },
    )
    monkeypatch.setattr(adapter, "find_run", lambda _: pytest.fail("must not query a posted dispatch"))
    monkeypatch.setattr(adapter, "post_result", lambda _: pytest.fail("must not repost a posted dispatch"))

    assert adapter.run(str(task_file)) == 0


def test_unbound_posted_state_cannot_silently_skip_work(tmp_path: Path):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.write_state(
        task_file,
        {"dispatch_id": "dispatch-1", "status": "POSTED"},
    )

    with pytest.raises(ValueError, match="missing bound task packet"):
        adapter.run(str(task_file))


def test_same_dispatch_with_different_task_identity_fails_closed(tmp_path: Path):
    original = packet()
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet(task_id="different-task")), encoding="utf-8")
    adapter.write_state(
        task_file,
        {
            "dispatch_id": "dispatch-1",
            "task_identity_sha256": adapter.task_identity_sha256(original),
            "task_packet_sha256": adapter.task_packet_sha256(original),
            "status": "WAITING_FOR_WORKER",
        },
    )

    with pytest.raises(ValueError, match="another task identity"):
        adapter.run(str(task_file))


def test_same_identity_with_mutated_payload_fails_closed(tmp_path: Path):
    original = packet(input="original")
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet(input="mutated")), encoding="utf-8")
    adapter.write_state(
        task_file,
        {
            "dispatch_id": "dispatch-1",
            "task_identity_sha256": adapter.task_identity_sha256(original),
            "task_packet_sha256": adapter.task_packet_sha256(original),
            "status": "WAITING_FOR_WORKER",
        },
    )

    with pytest.raises(ValueError, match="another task packet"):
        adapter.run(str(task_file))


def test_persisted_state_for_another_dispatch_fails_closed(tmp_path: Path):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.write_state(
        task_file,
        {"dispatch_id": "different-dispatch", "status": "WAITING_FOR_WORKER"},
    )

    with pytest.raises(ValueError, match="another dispatch"):
        adapter.run(str(task_file))


def test_duplicate_hosted_runs_for_one_dispatch_fail_closed(monkeypatch):
    monkeypatch.setattr(
        adapter,
        "run_cmd",
        lambda _: (
            0,
            json.dumps(
                [
                    {
                        "databaseId": 4,
                        "status": "completed",
                        "displayTitle": "Courier dispatch dispatch-1",
                    },
                    {
                        "databaseId": 5,
                        "status": "completed",
                        "displayTitle": "Courier dispatch dispatch-1",
                    },
                ]
            ),
            "",
        ),
    )

    with pytest.raises(RuntimeError, match="multiple GitHub runs"):
        adapter.find_run("dispatch-1")


def test_dispatch_preserves_taskpacket_as_raw_json(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    monkeypatch.setattr(adapter, "find_run", lambda _: (None, None))
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    commands = []
    monkeypatch.setattr(adapter, "run_cmd", lambda command: (commands.append(command) or (0, "branch", "")))
    assert adapter.run(str(task_file)) == 0
    dispatch = next(command for command in commands if command[:3] == ["gh", "workflow", "run"])
    assert "--raw-field" in dispatch
    encoded = dispatch[dispatch.index("--raw-field") + 1].removeprefix("task_payload_base64=")
    assert json.loads(base64.b64decode(encoded))["dispatch_id"] == "dispatch-1"


def test_durable_result_preserves_github_run_attempt():
    task = {**packet(), "execution_ref": "ref"}
    result = {
        **packet(), "execution_ref": "ref", "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1",
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
