"""Windows negatives that were not already on integration/v1.

RESULT_READY is the worker's local phase. The server ack is
ACK_RESULT_RECEIVED for the first matching post and ACK_DUPLICATE for the
same post again. A crash after that ack, before the local state file is
removed, must not run the provider a second time and must not turn the
accepted result into a rejection.

LeaseStore.release must ignore a foreign holder, a live holder presenting
the wrong fencing token, and an expired holder whose token has already
been replaced.

Host-loop DONE without journal proof is not repeated here. That negative
set is on PR #836, head ad50f362a3d80501d2f3d3630d389be5ab5e0745.
A second Windows process failing to take the worker lock is already
test_windows_writer_lease_cross_process_mutual_exclusion.
"""
import json
from dataclasses import replace

import pytest

from courier_runtime.lease import LeaseStore, StaleLease
from tests.test_windows_worker_contract import (
    Bridge,
    central,
    go,
    load_daemon,
    load_daemon_again,
    state_file,
)


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def leases(tmp_path):
    clock = Clock()
    store = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    yield store, clock
    store.close()


def test_foreign_release_does_not_clear_a_live_lease(leases):
    store, _ = leases
    live = store.acquire("worker:win-01", "win-01:10:1.0000:owner", "daemon_loop", ttl_s=30)
    foreign = replace(live, holder="win-01:99:2.0000:stranger", workkey="stolen")
    store.release(foreign)
    current = store.current("worker:win-01")
    assert current is not None
    assert current.holder == live.holder
    assert current.token == live.token
    assert store.check_write("worker:win-01", live.token).holder == live.holder


def test_wrong_token_does_not_release_the_live_lease(leases):
    store, _ = leases
    live = store.acquire("worker:win-01", "win-01:10:1.0000:owner", "daemon_loop", ttl_s=30)
    forged = replace(live, token=live.token + 1)
    store.release(forged)
    current = store.current("worker:win-01")
    assert current is not None
    assert current.holder == live.holder
    assert current.token == live.token
    assert current.workkey == live.workkey
    assert store.check_write(
        "worker:win-01", live.token, holder=live.holder, workkey=live.workkey
    ).token == live.token
    with pytest.raises(StaleLease):
        store.check_write(
            "worker:win-01", forged.token, holder=live.holder, workkey=live.workkey
        )


def test_expired_holder_cannot_release_the_successor_lease(leases):
    store, clock = leases
    old = store.acquire("worker:win-01", "win-01:10:1.0000:owner", "daemon_loop", ttl_s=30)
    clock.t += 31
    new = store.acquire("worker:win-01", "win-01:20:3.0000:next", "daemon_loop", ttl_s=30)
    assert new.token == old.token + 1
    store.release(old)
    current = store.current("worker:win-01")
    assert current is not None
    assert current.holder == new.holder
    assert current.token == new.token
    with pytest.raises(StaleLease):
        store.check_write("worker:win-01", old.token)
    assert store.check_write("worker:win-01", new.token).holder == new.holder


def test_crash_after_result_ack_does_not_execute_the_provider_again(tmp_path, monkeypatch):
    srv, http, headers = central(tmp_path, monkeypatch)
    daemon, executions = load_daemon(tmp_path, monkeypatch), []
    monkeypatch.chdir(daemon.APP_DATA_DIR)
    saved = {}
    real_persist = daemon.persist_task

    def remember(path, task):
        if task.get("worker_phase") == "RESULT_READY":
            saved["task"] = json.loads(json.dumps(task))
        return real_persist(path, task)

    monkeypatch.setattr(daemon, "persist_task", remember)
    go(daemon, monkeypatch, Bridge(http, headers, max_calls=6), executions,
       effect=daemon.APP_DATA_DIR / "effect.txt", tmp_path=tmp_path)

    assert executions == ["task-1"]
    assert saved["task"]["worker_phase"] == "RESULT_READY"
    assert srv.load_state()["tasks"]["task-1"]["status"] == "RESULT_RECEIVED"
    assert not state_file(daemon).exists()

    # The ack was received and the process died before deleting the local phase.
    state_file(daemon).parent.mkdir(parents=True, exist_ok=True)
    state_file(daemon).write_text(json.dumps(saved["task"]), encoding="utf-8")
    daemon2 = load_daemon_again(tmp_path, monkeypatch)
    bridge = Bridge(http, headers, max_calls=4)
    go(daemon2, monkeypatch, bridge, executions, tmp_path=tmp_path)

    assert executions == ["task-1"]
    assert bridge.posted("/tasks/result") == [saved["task"]["result_payload"]]
    task = srv.load_state()["tasks"]["task-1"]
    assert task["status"] == "RESULT_RECEIVED"
    assert task["result"]["dispatch_id"] == saved["task"]["result_payload"]["dispatch_id"]
    assert srv.load_state()["workers"]["WIN-01"]["current_task"] is None
    assert not state_file(daemon2).exists()
