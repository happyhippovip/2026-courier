from tests.controller.ctrl_helpers import make_controller, task_body
from courier_core.events import Event, EventType
from courier_core.state_machine import TaskStatus
import os
import sqlite3

def test_queued_task_with_cancel_request_is_cancelled_on_restart(tmp_path):
    ctl = make_controller(tmp_path / "home")
    _, body = ctl.create_task(task_body())
    task_id = body["task_id"]
    ctl.stop()
    
    # Simulate a crash right between TASK_CANCEL_REQUESTED and TASK_CANCELLED
    # by writing directly to the journal.
    from courier_core.journal import Journal
    with Journal(tmp_path / "home" / "courier.db") as journal:
        journal.append(Event(type=EventType.TASK_CANCEL_REQUESTED, task_id=task_id, payload={}))
    
    # Now reboot
    ctl2 = make_controller(tmp_path / "home")
    try:
        task = ctl2.journal.task(task_id)
        # R04 checks if it correctly recovered and applied TASK_CANCELLED
        assert task.status == TaskStatus.CANCELLED
    finally:
        ctl2.stop()
