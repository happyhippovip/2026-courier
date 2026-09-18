import json
from pathlib import Path

import pytest

from scripts import revenue_worker_adapter as adapter


def task(**changes):
    value = {
        "goal_id": "goal-1",
        "task_id": "../../outside",
        "attempt_id": "attempt-1",
        "dispatch_id": "dispatch-1",
        "execution_ref": "exec-1",
    }
    value.update(changes)
    return value


def test_work_directory_is_dispatch_bound_and_confined(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path)

    work_dir = adapter.work_dir_for_task(task())

    assert work_dir.parent == tmp_path
    assert "outside" not in work_dir.name


def test_result_identity_is_deterministic_for_transport_retry():
    packet = task()
    assert adapter.result_id_for(packet) == adapter.result_id_for(packet) == "result-dispatch-1"


def test_missing_identity_fails_before_filesystem_use(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path)
    with pytest.raises(ValueError, match="dispatch_id"):
        adapter.work_dir_for_task(task(dispatch_id=None))
    assert list(tmp_path.iterdir()) == []


def test_unacknowledged_result_remains_durable_and_retries_before_claim(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path)
    packet = task()
    work_dir = adapter.work_dir_for_task(packet)
    payload = {"result_id": adapter.result_id_for(packet), "status": "SUCCESS"}
    adapter.persist_pending_result(work_dir, payload)
    responses = iter([None, {"status": "ACK_RESULT_RECEIVED"}])
    monkeypatch.setattr(adapter, "http_post", lambda *args, **kwargs: next(responses))

    with pytest.raises(adapter.ResultPostError, match="not canonically acknowledged"):
        adapter.flush_pending_results({})
    assert json.loads((work_dir / "pending_result.json").read_text(encoding="utf-8")) == payload

    adapter.flush_pending_results({})
    assert not (work_dir / "pending_result.json").exists()
    marker = json.loads((work_dir / "posted_result.json").read_text(encoding="utf-8"))
    assert marker == {
        "acknowledgement": "ACK_RESULT_RECEIVED",
        "result_id": "result-dispatch-1",
    }


def test_generic_ignored_response_is_not_completion(monkeypatch):
    monkeypatch.setattr(adapter, "http_post", lambda *args, **kwargs: {"status": "IGNORED"})
    with pytest.raises(adapter.ResultPostError, match="not canonically acknowledged"):
        adapter.post_result({}, {"result_id": "result-1"})


def test_conflicting_pending_result_never_overwrites_authoritative_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path)
    work_dir = adapter.work_dir_for_task(task())
    original = {"result_id": "result-dispatch-1", "status": "SUCCESS"}
    adapter.persist_pending_result(work_dir, original)

    with pytest.raises(RuntimeError, match="conflicting pending result"):
        adapter.persist_pending_result(
            work_dir,
            {"result_id": "result-dispatch-1", "status": "FAILED_TERMINAL"},
        )

    assert json.loads((work_dir / "pending_result.json").read_text(encoding="utf-8")) == original


def test_restart_resumes_incomplete_read_only_task_before_new_claim(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path)
    packet = task(worker_id="REVENUE-1")
    work_dir = adapter.work_dir_for_task(packet)
    work_dir.mkdir()
    (work_dir / "task.json").write_text(json.dumps(packet), encoding="utf-8")
    resumed = []
    monkeypatch.setattr(
        adapter,
        "process_claimed_task",
        lambda config, worker_id, value, resume=False: resumed.append(
            (worker_id, value["dispatch_id"], resume)
        ),
    )

    assert adapter.recover_incomplete_tasks({}, "REVENUE-1") is True
    assert resumed == [("REVENUE-1", "dispatch-1", True)]


def test_restart_does_not_replay_posted_task(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path)
    packet = task(worker_id="REVENUE-1")
    work_dir = adapter.work_dir_for_task(packet)
    work_dir.mkdir()
    (work_dir / "task.json").write_text(json.dumps(packet), encoding="utf-8")
    (work_dir / "posted_result.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        adapter,
        "process_claimed_task",
        lambda *args, **kwargs: pytest.fail("posted task must not replay"),
    )

    assert adapter.recover_incomplete_tasks({}, "REVENUE-1") is False


def test_task_checkpoint_is_immutable_and_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path)
    packet = task()
    work_dir = adapter.work_dir_for_task(packet)
    work_dir.mkdir()

    checkpoint = adapter.persist_task_checkpoint(work_dir, packet)
    adapter.persist_task_checkpoint(work_dir, packet)
    with pytest.raises(RuntimeError, match="conflicting task checkpoint"):
        adapter.persist_task_checkpoint(work_dir, {**packet, "target_sha": "different"})

    assert json.loads(checkpoint.read_text(encoding="utf-8")) == packet
    assert list(work_dir.glob(".*.tmp")) == []
