"""Hub Home board must survive a task row with an unknown status.

A journal written by a newer controller (or any forward-compat status) must
degrade to one unrecognised card, never fail the whole board read.
"""

from courier_core import projection
from courier_core.journal import Journal
from courier_core.state_machine import TaskState, TaskStatus
from courier_hub import model
from courier_hub.server import Hub


def _state(task_id):
    return TaskState(task_id=task_id, status=TaskStatus.RUNNING, adapter="synthetic",
                     params={}, effect_class="non_idempotent", max_attempts=3,
                     lease_ttl_s=6, timeout_s=None, attempt=1)


def _seed(home):
    journal = Journal(home / "courier.db").open()
    try:
        projection.store(journal.conn, _state("t-ok"), 1)
        projection.store(journal.conn, _state("t-future"), 1)
        journal.conn.execute("UPDATE tasks SET status='FUTURE_STATUS_X' WHERE task_id='t-future'")
    finally:
        journal.close()


def _ids(tasks):
    return {t["task_id"] if isinstance(t, dict) else t.task_id for t in tasks}


def test_read_survives_unknown_status(tmp_path):
    _seed(tmp_path)
    hub = Hub(tmp_path, controller_url="http://127.0.0.1:9")
    tasks, _, _ = hub._read()
    assert _ids(tasks) == {"t-ok", "t-future"}


def test_home_shows_unrecognised_card_for_unknown_status(tmp_path):
    _seed(tmp_path)
    hub = Hub(tmp_path, controller_url="http://127.0.0.1:9")
    tasks, events_by_task, _ = hub._read()
    view = model.home(tasks, events_by_task)
    future = [c for c in view["working"] if c["id"] == "t-future"]
    assert len(future) == 1
    assert future[0]["phase"] == "unrecognised"
    assert view["counts"]["working"] == 2
