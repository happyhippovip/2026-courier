"""Unit tests for courier_core.result_digest (P2)."""

import hashlib
import json
import sqlite3
import pytest
from pathlib import Path

from courier_core.journal import Journal
from courier_core.events import Event, EventType
from courier_core.result_digest import summarize_home, main, ResultDigest


def test_summarize_home_not_found(tmp_path):
    digest = summarize_home(tmp_path / "nonexistent")
    assert digest.status == "NOT_FOUND"
    assert digest.total_accepted == 0
    assert digest.error_detail is not None


def test_summarize_home_corrupt(tmp_path):
    home = tmp_path / "corrupt_home"
    home.mkdir()
    db = home / "courier.db"
    db.write_bytes(b"NOT A SQLITE FILE GARBAGE HEADER 1234567890")

    digest = summarize_home(home)
    assert digest.status == "CORRUPT"
    assert digest.total_accepted == 0


def test_summarize_home_empty_db_no_events_table(tmp_path):
    home = tmp_path / "empty_home"
    home.mkdir()
    db = home / "courier.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE foo (x INTEGER);")
    conn.commit()
    conn.close()

    digest = summarize_home(home)
    assert digest.status == "EMPTY"
    assert digest.total_accepted == 0


def test_summarize_home_zero_accepted(tmp_path):
    home = tmp_path / "zero_accepted"
    journal = Journal(home / "courier.db").open()
    journal.append(Event(EventType.CONTROLLER_STARTED))
    journal.close()

    digest = summarize_home(home)
    assert digest.status == "OK"
    assert digest.total_accepted == 0
    assert digest.total_artifacts == 0
    assert digest.adapters == []
    assert digest.tasks == []
    assert digest.digest_sha256 == hashlib.sha256(b"[]").hexdigest()


def test_summarize_home_with_accepted_results(tmp_path):
    home = tmp_path / "normal_home"
    journal = Journal(home / "courier.db").open()

    # Task 1: synthetic adapter with 2 artifacts
    task1_created = Event(
        EventType.TASK_CREATED,
        task_id="task-001",
        payload={
            "adapter": "synthetic",
            "params": {"write": "out.txt"},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 30,
        },
    )
    journal.append(task1_created)
    journal.append(Event(EventType.TASK_CLAIMED, task_id="task-001", attempt=1, dispatch_id="disp-1", worker_id="w1", payload={"ttl_s": 30}))
    journal.append(Event(EventType.TASK_STARTED, task_id="task-001", attempt=1, dispatch_id="disp-1", worker_id="w1"))
    art1_sha = "a" * 64
    art2_sha = "b" * 64
    journal.append(Event(
        EventType.RESULT_READY,
        task_id="task-001",
        attempt=1,
        dispatch_id="disp-1",
        worker_id="w1",
        result_id="res-1",
        payload={
            "outcome": "success",
            "artifacts": [
                {"path": "out.txt", "sha256": art1_sha},
                {"path": "log.txt", "sha256": art2_sha},
            ],
        },
    ))
    journal.append(Event(
        EventType.RESULT_ACCEPTED,
        task_id="task-001",
        attempt=1,
        dispatch_id="disp-1",
        result_id="res-1",
    ))

    # Task 2: local_json_delivery with 1 artifact
    task2_created = Event(
        EventType.TASK_CREATED,
        task_id="task-002",
        payload={
            "adapter": "local_json_delivery",
            "params": {"article_id": "art-1"},
            "effect_class": "idempotent",
            "max_attempts": 2,
            "lease_ttl_s": 30,
        },
    )
    journal.append(task2_created)
    journal.append(Event(EventType.TASK_CLAIMED, task_id="task-002", attempt=1, dispatch_id="disp-2", worker_id="w2", payload={"ttl_s": 30}))
    journal.append(Event(EventType.TASK_STARTED, task_id="task-002", attempt=1, dispatch_id="disp-2", worker_id="w2"))
    art3_sha = "c" * 64
    journal.append(Event(
        EventType.RESULT_READY,
        task_id="task-002",
        attempt=1,
        dispatch_id="disp-2",
        worker_id="w2",
        result_id="res-2",
        payload={
            "outcome": "success",
            "artifacts": [{"path": "delivered_articles/art-1.json", "sha256": art3_sha}],
        },
    ))
    journal.append(Event(
        EventType.RESULT_ACCEPTED,
        task_id="task-002",
        attempt=1,
        dispatch_id="disp-2",
        result_id="res-2",
    ))

    journal.close()

    # Now summarize
    digest = summarize_home(home)
    assert digest.status == "OK"
    assert digest.total_accepted == 2
    assert digest.total_artifacts == 3
    assert digest.adapters == ["local_json_delivery", "synthetic"]
    assert len(digest.tasks) == 2

    t1 = next(t for t in digest.tasks if t["task_id"] == "task-001")
    assert t1["adapter"] == "synthetic"
    assert t1["outcome"] == "success"
    assert len(t1["artifacts"]) == 2
    assert t1["artifacts"][0]["path"] == "out.txt"

    t2 = next(t for t in digest.tasks if t["task_id"] == "task-002")
    assert t2["adapter"] == "local_json_delivery"
    assert len(t2["artifacts"]) == 1

    # Determinism: repeating the call yields the exact same digest_sha256
    digest2 = summarize_home(home)
    assert digest.digest_sha256 == digest2.digest_sha256
    assert len(digest.digest_sha256) == 64


def test_summarize_home_read_only_never_alters_db(tmp_path):
    home = tmp_path / "ro_home"
    journal = Journal(home / "courier.db").open()
    journal.append(Event(EventType.CONTROLLER_STARTED))
    journal.close()

    db_path = home / "courier.db"
    initial_bytes = db_path.read_bytes()

    summarize_home(home)
    after_bytes = db_path.read_bytes()
    assert initial_bytes == after_bytes


def test_cli_invocation(tmp_path, capsys):
    home = tmp_path / "cli_home"
    journal = Journal(home / "courier.db").open()
    journal.append(Event(EventType.CONTROLLER_STARTED))
    journal.close()

    ret = main(["--home", str(home), "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "OK"
    assert data["total_accepted"] == 0

    # Human-readable output
    ret2 = main(["--home", str(home)])
    assert ret2 == 0
    captured2 = capsys.readouterr()
    assert "Status: OK" in captured2.out
    assert "Total Accepted Tasks: 0" in captured2.out


def test_summarize_home_with_rejected_results(tmp_path):
    home = tmp_path / "rejected_home"
    journal = Journal(home / "courier.db").open()

    task_created = Event(
        EventType.TASK_CREATED,
        task_id="task-rej-01",
        payload={
            "adapter": "synthetic",
            "params": {"write": "out.txt"},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 30,
        },
    )
    journal.append(task_created)
    journal.append(Event(EventType.TASK_CLAIMED, task_id="task-rej-01", attempt=1, dispatch_id="disp-rej-1", worker_id="w1", payload={"ttl_s": 30}))
    journal.append(Event(EventType.TASK_STARTED, task_id="task-rej-01", attempt=1, dispatch_id="disp-rej-1", worker_id="w1"))
    journal.append(Event(
        EventType.RESULT_READY,
        task_id="task-rej-01",
        attempt=1,
        dispatch_id="disp-rej-1",
        worker_id="w1",
        result_id="res-rej-1",
        payload={"outcome": "failure", "artifacts": []},
    ))
    journal.append(Event(
        EventType.RESULT_REJECTED,
        task_id="task-rej-01",
        attempt=1,
        dispatch_id="disp-rej-1",
        result_id="res-rej-1",
        payload={"reason": "compilation error", "retryable": True},
    ))
    journal.close()

    digest = summarize_home(home)
    assert digest.status == "OK"
    assert digest.total_accepted == 0
    assert digest.total_rejected == 1
    assert digest.total_artifacts == 0
    assert digest.adapters == ["synthetic"]
    assert digest.tasks == []
    assert len(digest.rejected_tasks) == 1

    rej = digest.rejected_tasks[0]
    assert rej["task_id"] == "task-rej-01"
    assert rej["result_id"] == "res-rej-1"
    assert rej["adapter"] == "synthetic"
    assert rej["reason"] == "compilation error"
    assert rej["retryable"] is True


def test_summarize_home_with_mixed_accepted_and_rejected(tmp_path):
    home = tmp_path / "mixed_home"
    journal = Journal(home / "courier.db").open()

    # Accepted task
    journal.append(Event(
        EventType.TASK_CREATED,
        task_id="task-acc",
        payload={"adapter": "synthetic", "params": {}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 30},
    ))
    journal.append(Event(EventType.TASK_CLAIMED, task_id="task-acc", attempt=1, dispatch_id="d1", worker_id="w1", payload={"ttl_s": 30}))
    journal.append(Event(EventType.TASK_STARTED, task_id="task-acc", attempt=1, dispatch_id="d1", worker_id="w1"))
    journal.append(Event(
        EventType.RESULT_READY,
        task_id="task-acc", attempt=1, dispatch_id="d1", worker_id="w1", result_id="r1",
        payload={"outcome": "success", "artifacts": [{"path": "ok.txt", "sha256": "1" * 64}]},
    ))
    journal.append(Event(EventType.RESULT_ACCEPTED, task_id="task-acc", attempt=1, dispatch_id="d1", result_id="r1"))

    # Rejected task
    journal.append(Event(
        EventType.TASK_CREATED,
        task_id="task-rej",
        payload={"adapter": "local_json_delivery", "params": {}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 30},
    ))
    journal.append(Event(EventType.TASK_CLAIMED, task_id="task-rej", attempt=1, dispatch_id="d2", worker_id="w2", payload={"ttl_s": 30}))
    journal.append(Event(EventType.TASK_STARTED, task_id="task-rej", attempt=1, dispatch_id="d2", worker_id="w2"))
    journal.append(Event(
        EventType.RESULT_READY,
        task_id="task-rej", attempt=1, dispatch_id="d2", worker_id="w2", result_id="r2",
        payload={"outcome": "failure", "artifacts": []},
    ))
    journal.append(Event(
        EventType.RESULT_REJECTED,
        task_id="task-rej", attempt=1, dispatch_id="d2", result_id="r2",
        payload={"reason": "schema mismatch", "retryable": False},
    ))
    journal.close()

    digest = summarize_home(home)
    assert digest.status == "OK"
    assert digest.total_accepted == 1
    assert digest.total_rejected == 1
    assert digest.total_artifacts == 1
    assert sorted(digest.adapters) == ["local_json_delivery", "synthetic"]
    assert len(digest.tasks) == 1
    assert len(digest.rejected_tasks) == 1
    assert digest.tasks[0]["task_id"] == "task-acc"
    assert digest.rejected_tasks[0]["task_id"] == "task-rej"
    assert digest.rejected_tasks[0]["reason"] == "schema mismatch"


def test_cli_invocation_shows_rejected_tasks(tmp_path, capsys):
    home = tmp_path / "cli_rej_home"
    journal = Journal(home / "courier.db").open()
    journal.append(Event(
        EventType.TASK_CREATED,
        task_id="t-rej",
        payload={"adapter": "synthetic", "params": {}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 30},
    ))
    journal.append(Event(EventType.TASK_CLAIMED, task_id="t-rej", attempt=1, dispatch_id="d1", worker_id="w1", payload={"ttl_s": 30}))
    journal.append(Event(EventType.TASK_STARTED, task_id="t-rej", attempt=1, dispatch_id="d1", worker_id="w1"))
    journal.append(Event(
        EventType.RESULT_READY,
        task_id="t-rej", attempt=1, dispatch_id="d1", worker_id="w1", result_id="r1",
        payload={"outcome": "failure", "artifacts": []},
    ))
    journal.append(Event(
        EventType.RESULT_REJECTED,
        task_id="t-rej", attempt=1, dispatch_id="d1", result_id="r1",
        payload={"reason": "fatal timeout", "retryable": False},
    ))
    journal.close()

    # JSON mode
    ret = main(["--home", str(home), "--json"])
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_accepted"] == 0
    assert data["total_rejected"] == 1
    assert len(data["rejected_tasks"]) == 1
    assert data["rejected_tasks"][0]["reason"] == "fatal timeout"

    # Human-readable mode
    ret2 = main(["--home", str(home)])
    assert ret2 == 0
    out2 = capsys.readouterr().out
    assert "Total Accepted Tasks: 0" in out2
    assert "Total Rejected Tasks: 1" in out2
