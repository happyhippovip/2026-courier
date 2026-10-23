"""An error inside verification must leave the journaled result queued."""

import queue
import sqlite3

from ctrl_helpers import Verifiers, make_controller, run_attempt, task_body
from courier_core.controller import Controller
from courier_core.verification import Verdict


def test_verify_task_error_keeps_the_result_queued(tmp_path, monkeypatch):
    def verify(task, result, home):
        return Verdict(True, "resumed")

    ctl = make_controller(tmp_path / "home", verifier=Verifiers(probe=verify))
    try:
        _, body = ctl.create_task(task_body(max_attempts=1))
        task_id = body["task_id"]
        run_attempt(ctl)
        original = Controller._verify_task

        def boom(self, tid):
            raise sqlite3.OperationalError("disk")

        monkeypatch.setattr(Controller, "_verify_task", boom)
        caught = None
        try:
            ctl.verify_next()
        except sqlite3.OperationalError as exc:
            caught = type(exc).__name__
        except Exception as exc:
            caught = type(exc).__name__
        try:
            queued = ctl._verify_queue.get_nowait()
        except queue.Empty:
            queued = "EMPTY"
        else:
            ctl._verify_queue.put(queued)
        status = ctl.journal.task(task_id).status.value
        assert (caught, queued, status) == ("OperationalError", task_id, "VERIFYING")
        monkeypatch.setattr(Controller, "_verify_task", original)
        ctl.drain()
        assert ctl.journal.task(task_id).status.value == "COMPLETE"
    finally:
        ctl.stop()
