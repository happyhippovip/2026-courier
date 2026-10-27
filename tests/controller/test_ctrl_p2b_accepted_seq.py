"""P2b: task_result exposes the journal seq of RESULT_ACCEPTED (accepted_seq)."""

import pytest

from ctrl_helpers import make_controller, run_attempt, task_body
from courier_core.events import EventType


@pytest.fixture
def ctl(tmp_path):
    controller = make_controller(tmp_path / "home")
    yield controller
    controller.stop()


def test_task_result_accepted_seq_is_the_result_accepted_journal_seq(ctl):
    code, created = ctl.create_task(task_body())
    assert code == 201
    task_id = created["task_id"]
    run_attempt(ctl, result_id="r1")
    ctl.drain()
    body = ctl.task_result(task_id)
    accepted = [e for e in ctl.journal.events(task_id=task_id)
                if e.type is EventType.RESULT_ACCEPTED and e.result_id == "r1"]
    assert len(accepted) == 1
    assert body["result_id"] == "r1"
    assert isinstance(body["accepted_seq"], int) and not isinstance(body["accepted_seq"], bool)
    assert body["accepted_seq"] == accepted[0].seq > 0
    ready = [e for e in ctl.journal.events(task_id=task_id) if e.type is EventType.RESULT_READY]
    assert body["accepted_seq"] > ready[-1].seq
