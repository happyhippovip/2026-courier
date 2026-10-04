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


def _success_result(path, digest):
    task = packet()
    return task, {
        **task,
        "run_id": "99",
        "run_attempt": "1",
        "result_id": "result-dispatch-1",
        "status": "SUCCESS",
        "operation": "deterministic_transform",
        "artifacts": [{"path": path, "sha256": digest}],
    }


def _success_evidence():
    return {"operation": "deterministic_transform",
            "input_sha256": hashlib.sha256(b"canary").hexdigest()}


@pytest.mark.parametrize("evil_path", ["/etc/passwd", "../outside.txt", "sub/../../outside.txt"])
def test_verify_result_rejects_evidence_path_outside_download_directory(tmp_path: Path, evil_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"not-the-worker-output\n")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    path = str(outside) if evil_path.startswith("/") else evil_path
    task, result = _success_result(path, digest)
    with pytest.raises(ValueError, match="escapes the download directory"):
        adapter.verify_result(task, result, _success_evidence(), "99", tmp_path / "download")


@pytest.mark.parametrize("bad_path", [None, 42, ["x"], ""])
def test_verify_result_rejects_non_string_evidence_path(tmp_path: Path, bad_path):
    task, result = _success_result(bad_path, "x")
    with pytest.raises(ValueError, match="escapes the download directory"):
        adapter.verify_result(task, result, _success_evidence(), "99", tmp_path)


def test_verify_result_accepts_evidence_inside_download_directory(tmp_path: Path):
    directory = tmp_path / "download"
    directory.mkdir()
    blob = directory / "courier_output_dispatch-1.json"
    blob.write_bytes(b"worker-output\n")
    task, result = _success_result(
        "courier_output_dispatch-1.json", hashlib.sha256(b"worker-output\n").hexdigest())
    assert adapter.verify_result(task, result, _success_evidence(), "99", directory) is None


def _completed_run_result(blob_digest):
    task = packet()
    return task, {
        **task,
        "run_id": "99",
        "run_attempt": "1",
        "result_id": "result-dispatch-1",
        "status": "SUCCESS",
        "operation": "deterministic_transform",
        "artifacts": [{"path": "out.bin", "sha256": blob_digest}],
    }


def test_run_posts_verified_result_and_records_posted_state(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    blob = b"worker-output\n"
    task, result = _completed_run_result(hashlib.sha256(blob).hexdigest())
    evidence = _success_evidence()
    posted = []
    monkeypatch.setattr(adapter, "find_run", lambda _: ("99", "completed"))

    def fake_download(run_id, dispatch_id, directory):
        assert (run_id, dispatch_id) == ("99", "dispatch-1")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"result_{dispatch_id}.json").write_text(json.dumps(result), encoding="utf-8")
        (directory / "out.bin").write_bytes(blob)
        return result, evidence

    monkeypatch.setattr(adapter, "download_result", fake_download)
    monkeypatch.setattr(adapter, "post_result", posted.append)
    assert adapter.run(str(task_file)) == 0
    assert [p["result_id"] for p in posted] == ["result-dispatch-1"]
    state = json.loads(adapter.state_path(task_file).read_text(encoding="utf-8"))
    assert state["status"] == "POSTED" and state["run_id"] == "99"
    assert not (tmp_path / ".courier-result-dispatch-1").exists()


def test_run_with_tampered_evidence_posts_nothing_and_cleans_up(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    _, result = _completed_run_result(hashlib.sha256(b"worker-output\n").hexdigest())
    posted = []
    monkeypatch.setattr(adapter, "find_run", lambda _: ("99", "completed"))

    def fake_download_tampered(run_id, dispatch_id, directory):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "out.bin").write_bytes(b"tampered\n")
        return result, _success_evidence()

    monkeypatch.setattr(adapter, "download_result", fake_download_tampered)
    monkeypatch.setattr(adapter, "post_result", posted.append)
    with pytest.raises(ValueError, match="hash does not match"):
        adapter.run(str(task_file))
    assert posted == []
    assert not (tmp_path / ".courier-result-dispatch-1").exists()


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
    assert adapter.run(str(task_file)) == 0


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
