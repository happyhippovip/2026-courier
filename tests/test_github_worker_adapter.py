import base64
import hashlib
import json
from pathlib import Path

import pytest

from scripts import github_worker_adapter as adapter
from scripts.integration_contract import canonical_result_id, validate_durable_result


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
        **packet(), "run_id": "99", "run_attempt": "1",
        "status": "SUCCESS", "artifacts": [{"path": "courier_output_dispatch-1.json", "sha256": "a" * 64}],
    }
    result["result_id"] = canonical_result_id(result)
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


def test_verify_result_mismatches(tmp_path: Path):
    task = packet()
    # Identity mismatch
    res = {**task, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "task_id": "wrong"}
    with pytest.raises(ValueError, match="identity does not match"):
        adapter.verify_result(task, res, None, "99", tmp_path)
    
    # Run ID mismatch
    res = {**task, "run_id": "98", "run_attempt": "1", "result_id": "result-dispatch-1"}
    with pytest.raises(ValueError, match="not bound to the observed"):
        adapter.verify_result(task, res, None, "99", tmp_path)

    # Missing run_attempt
    res = {**task, "run_id": "99", "result_id": "result-dispatch-1"}
    with pytest.raises(ValueError, match="missing GitHub run_attempt"):
        adapter.verify_result(task, res, None, "99", tmp_path)

    # Failed operation logic
    res = {**task, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "FAILED", "artifacts": ["x"]}
    with pytest.raises(ValueError, match="failed GitHub operation must not claim evidence"):
        adapter.verify_result(task, res, None, "99", tmp_path)
    
    res = {**task, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "FAILED", "artifacts": []}
    adapter.verify_result(task, res, None, "99", tmp_path) # Should pass

    # Not success
    res = {**task, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "RUNNING"}
    with pytest.raises(ValueError, match="did not succeed"):
        adapter.verify_result(task, res, None, "99", tmp_path)

    # Missing evidence
    res = {**task, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "SUCCESS", "operation": "deterministic_transform"}
    with pytest.raises(ValueError, match="missing evidence"):
        adapter.verify_result(task, res, None, "99", tmp_path)

    # Bad artifacts
    res["artifacts"] = []
    with pytest.raises(ValueError, match="requires one evidence artifact"):
        adapter.verify_result(task, res, {}, "99", tmp_path)

    res["artifacts"] = [{"path": "nonexistent"}]
    with pytest.raises(ValueError, match="evidence artifact hash does not match"):
        adapter.verify_result(task, res, {}, "99", tmp_path)

    # Proper artifact
    (tmp_path / "evi.json").write_bytes(b"content")
    hash_val = hashlib.sha256(b"content").hexdigest()
    res["artifacts"] = [{"path": "evi.json", "sha256": hash_val}]
    
    # Operation mismatch
    with pytest.raises(ValueError, match="evidence operation mismatch"):
        adapter.verify_result(task, res, {"operation": "wrong"}, "99", tmp_path)

    # Deterministic mismatch
    with pytest.raises(ValueError, match="deterministic transform acceptance failed"):
        adapter.verify_result(task, res, {"operation": "deterministic_transform", "input_sha256": "wrong"}, "99", tmp_path)

    # Report mismatch
    task_report = packet(task_type="report", report="x")
    res_report = {**task_report, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "SUCCESS", "operation": "report", "artifacts": [{"path": "evi.json", "sha256": hash_val}]}
    with pytest.raises(ValueError, match="report acceptance failed"):
        adapter.verify_result(task_report, res_report, {"operation": "report", "report": "y"}, "99", tmp_path)

    # verify_file mismatch
    task_vf = packet(task_type="verify_file", path="p")
    res_vf = {**task_vf, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "SUCCESS", "operation": "verify_file", "artifacts": [{"path": "evi.json", "sha256": hash_val}]}
    with pytest.raises(ValueError, match="file verification acceptance failed"):
        adapter.verify_result(task_vf, res_vf, {"operation": "verify_file", "path": "wrong"}, "99", tmp_path)

    # exit_code mismatch
    task_sa = packet(task_type="static_analysis")
    res_sa = {**task_sa, "run_id": "99", "run_attempt": "1", "result_id": "result-dispatch-1", "status": "SUCCESS", "operation": "static_analysis", "artifacts": [{"path": "evi.json", "sha256": hash_val}]}
    with pytest.raises(ValueError, match="bounded verification acceptance failed"):
        adapter.verify_result(task_sa, res_sa, {"operation": "static_analysis", "exit_code": 1}, "99", tmp_path)

def test_find_run_failures(monkeypatch):
    monkeypatch.setattr(adapter, "run_cmd", lambda _: (1, "", "error"))
    with pytest.raises(RuntimeError, match="cannot list workflow runs"):
        adapter.find_run("d")

    monkeypatch.setattr(adapter, "run_cmd", lambda _: (0, json.dumps([
        {"databaseId": 4, "status": "queued", "displayTitle": "Courier dispatch d"},
        {"databaseId": 5, "status": "completed", "displayTitle": "Courier dispatch d"}
    ]), ""))
    with pytest.raises(RuntimeError, match="multiple GitHub runs found"):
        adapter.find_run("d")

def test_download_result_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "run_cmd", lambda _: (1, "", "error"))
    with pytest.raises(RuntimeError, match="cannot download"):
        adapter.download_result("99", "d", tmp_path)

    monkeypatch.setattr(adapter, "run_cmd", lambda _: (0, "", ""))
    with pytest.raises(ValueError, match="exactly one result"):
        adapter.download_result("99", "d", tmp_path)

def test_post_result_failures(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="COURIER_API_KEY is required"):
        adapter.post_result({})

    class Response:
        status_code = 400
        text = "Bad Request"
    monkeypatch.setenv("COURIER_API_KEY", "x")
    monkeypatch.setattr(adapter.requests, "post", lambda *a, **k: Response())
    with pytest.raises(RuntimeError, match="Courier result POST failed"):
        adapter.post_result({})

def test_run_failures_and_state(tmp_path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    
    # Prior state wrong dispatch
    adapter.write_state(task_file, {"dispatch_id": "wrong"})
    with pytest.raises(ValueError, match="belongs to another dispatch"):
        adapter.run(str(task_file))

    # Prior state POSTED
    adapter.write_state(task_file, {"dispatch_id": "dispatch-1", "status": "POSTED"})
    assert adapter.run(str(task_file)) == 0

    # Workflow dispatch failed
    task_file.with_name(f"{task_file.stem}.github-worker-state.json").unlink()
    monkeypatch.setattr(adapter, "find_run", lambda _: (None, None))
    monkeypatch.setattr(adapter, "run_cmd", lambda cmd: (1, "", "") if cmd[0] == "gh" else (0, "ref", ""))
    with pytest.raises(RuntimeError, match="workflow dispatch failed"):
        adapter.run(str(task_file))

    # Ref fetch failed. Drop the DISPATCHING marker the previous section's
    # failed dispatch left behind: with a fresh marker present, resume would
    # honor the dispatch grace period and wait for a run that the mocked
    # find_run can never return (300 s of real sleeps -> timeout). The
    # marker belongs to the failed attempt, not to this section.
    task_file.with_name(f"{task_file.stem}.github-worker-state.json").unlink()
    monkeypatch.setenv("GITHUB_WORKER_REF", "")
    monkeypatch.setattr(adapter, "run_cmd", lambda cmd: (1, "", "") if cmd[0] == "git" else (0, "", ""))
    with pytest.raises(RuntimeError, match="cannot determine dispatch ref"):
        adapter.run(str(task_file))

def test_run_polling_timeout(tmp_path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "find_run", lambda _: ("99", "queued"))
    assert adapter.run(str(task_file)) == 0

import sys
import runpy
def test_main_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["", "nonexistent"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path("scripts/github_worker_adapter.py", run_name="__main__")
    assert "GITHUB_WORKER_ERROR=" in capsys.readouterr().err

def test_run_cmd():
    rc, out, err = adapter.run_cmd([sys.executable, "-c", "print('hello')"])
    assert rc == 0
    assert "hello" in out

def test_download_result_success(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "run_cmd", lambda _: (0, "", ""))
    res_dir = tmp_path / "res"
    res_dir.mkdir()
    (res_dir / "result_d.json").write_text('{"foo": "bar"}')
    (res_dir / "courier_output_d.json").write_text('{"evi": 1}')
    
    r, e = adapter.download_result("99", "d", res_dir)
    assert r["foo"] == "bar"
    assert e["evi"] == 1

def test_run_polling_loop(tmp_path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.write_state(task_file, {"dispatch_id": "dispatch-1", "status": "WAITING_FOR_WORKER"})
    
    time_calls = [0, 0.5, 1.5]
    monkeypatch.setattr(adapter.time, "monotonic", lambda: time_calls.pop(0))
    monkeypatch.setattr(adapter.time, "sleep", lambda _: None)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 1)
    monkeypatch.setattr(adapter, "find_run", lambda _: ("99", "in_progress"))
    
    adapter.run(str(task_file))
    state = json.loads(adapter.state_path(task_file).read_text())
    assert state["run_id"] == "99"
    assert state["status"] == "WAITING_FOR_WORKER"


def _workflow_python_blocks() -> list[str]:
    """Return the success and failure scripts embedded in courier_worker.yml."""
    lines = Path(".github/workflows/courier_worker.yml").read_text(encoding="utf-8").splitlines()
    blocks = []
    index = 0
    while index < len(lines):
        if "<<'PY'" not in lines[index]:
            index += 1
            continue
        index += 1
        body = []
        while index < len(lines) and lines[index].strip() != "PY":
            body.append(lines[index])
            index += 1
        if index >= len(lines) or not body:
            raise AssertionError("workflow heredoc is not closed")
        indent = len(body[0]) - len(body[0].lstrip(" "))
        blocks.append("\n".join(line[indent:] for line in body) + "\n")
        index += 1
    if len(blocks) != 2:
        raise AssertionError(f"courier_worker.yml must embed success and failure scripts, found {len(blocks)}")
    return blocks


def _claimed_github_task(tmp_path, monkeypatch):
    from server import app as server_app

    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    http = server_app.app.test_client()
    headers = {"Authorization": "Bearer test-secret"}
    registered = http.post(
        "/workers/register",
        headers=headers,
        json={"worker_id": "GITHUB-HOSTED", "platform": "github", "capabilities": ["github"]},
    )
    assert registered.status_code == 200
    created = http.post(
        "/goals",
        headers=headers,
        json={
            "goal_text": "one bounded github task",
            "workflow_plan": [
                {
                    "task_id": "task-gh",
                    "target_agent": "github",
                    "task_type": "metadata",
                    "instruction": "record source metadata",
                }
            ],
        },
    )
    assert created.status_code == 200
    claimed = http.post("/tasks/claim", headers=headers, json={"worker_id": "GITHUB-HOSTED"})
    assert claimed.status_code == 200
    task = claimed.get_json()["task"]
    assert task["worker_id"] == "GITHUB-HOSTED"
    return http, headers, task


def _run_workflow_block(block: str, task: dict, workdir: Path) -> dict:
    import os
    import subprocess

    workdir.mkdir(parents=True, exist_ok=True)
    script = workdir / "courier_task.py"
    script.write_text(block, encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "TASK_PAYLOAD_BASE64": base64.b64encode(json.dumps(task).encode()).decode(),
        "DISPATCH_ID": task["dispatch_id"],
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "99",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_JOB": "execute",
        "GITHUB_WORKSPACE": str(Path(".").resolve()),
    })
    completed = subprocess.run(
        [sys.executable, str(script)], cwd=workdir, env=env, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads((workdir / f"result_{task['dispatch_id']}.json").read_text(encoding="utf-8"))


def test_github_worker_result_post_is_accepted(tmp_path, monkeypatch):
    """A result the GitHub worker workflow actually writes must be accepted."""
    http, headers, task = _claimed_github_task(tmp_path, monkeypatch)
    success_block, failure_block = _workflow_python_blocks()
    success = _run_workflow_block(success_block, task, tmp_path / "success")
    posted = http.post("/tasks/result", headers=headers, json=success)
    assert posted.status_code == 200, posted.get_data(as_text=True)
    assert success["result_id"] == canonical_result_id(success)
    assert success["result_id"] != f"result-{task['dispatch_id']}"

    failed_http, failed_headers, failed_task = _claimed_github_task(tmp_path / "failed-state", monkeypatch)
    failed = _run_workflow_block(failure_block, failed_task, tmp_path / "failed")
    failed_post = failed_http.post("/tasks/result", headers=failed_headers, json=failed)
    assert failed_post.status_code == 200, failed_post.get_data(as_text=True)
    assert failed["status"] == "FAILED"
    assert failed["result_id"] == canonical_result_id(failed)

