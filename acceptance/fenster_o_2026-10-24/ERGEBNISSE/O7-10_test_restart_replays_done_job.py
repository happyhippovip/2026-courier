"""O7-10 (B5 Replay): a restart must not dispatch a job whose run already happened.

Guard (holds, tests/test_queue_redispatch_skip.py:51-64): an ADMITTED fingerprint
is skipped on restart, no second dispatch.
Defect (strict xfail): crash after ``gh workflow run`` succeeded but before
ADMITTED was saved leaves a DISPATCHING marker. Within the grace window a restart
adopts the run (scripts/intake_dispatcher.py:258-268, 284-301). After
INTAKE_DISPATCH_GRACE_SECONDS (300 s, :25) the marker counts as dead
(:269-283) and the restart calls ``gh workflow run`` again, without first
looking for the run that already exists. The customer's job runs a second time.
All subprocess calls are mocked: no gh, no network, 0 EUR.
"""
import json
import time
from datetime import datetime, timezone
from unittest import mock

import pytest

from scripts import queue_processor
import intake_dispatcher

INTAKE = {"customer_reference": "cust-1", "target_owner": "o", "target_repo": "r",
          "target_sha": "s", "paid": True}


def _layout(tmp_path, dispatched_at):
    (tmp_path / "intakes" / "pending").mkdir(parents=True)
    (tmp_path / "intakes" / "processed").mkdir(parents=True)
    (tmp_path / "intakes" / "pending" / "job.json").write_text(json.dumps(INTAKE))
    task_id = intake_dispatcher.fingerprint_task_id(INTAKE)
    (tmp_path / "central_state.json").write_text(json.dumps({"tasks": {task_id: {
        "task_id": task_id, "customer_reference": "cust-1",
        "admission": intake_dispatcher.ADMISSION_DISPATCHING, "dispatched_at": dispatched_at,
    }}}))


def _gh(existing_run_at):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out = mock.Mock(returncode=0, stderr="")
        if cmd[:3] == ["gh", "run", "list"]:
            created = datetime.fromtimestamp(existing_run_at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            out.stdout = json.dumps([{"databaseId": 777, "createdAt": created}])
        else:
            out.stdout = ""
        return out
    return calls, fake_run


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-10/B5: stale DISPATCHING marker -> restart re-dispatches a run that already happened")
def test_restart_after_grace_adopts_existing_run_instead_of_dispatching_again(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first_dispatch = time.time() - intake_dispatcher.INTAKE_DISPATCH_GRACE_SECONDS - 60
    _layout(tmp_path, first_dispatch)
    calls, fake_run = _gh(existing_run_at=first_dispatch + 5)   # the first dispatch did start a run
    with mock.patch.object(intake_dispatcher.subprocess, "run", side_effect=fake_run), \
         mock.patch.object(intake_dispatcher.time, "sleep", lambda s: None):
        queue_processor.process_queue()
    dispatches = [c for c in calls if c[:3] == ["gh", "workflow", "run"]]
    assert dispatches == [], f"{len(dispatches)} new dispatch(es) for a job that already ran"


def test_guard_restart_inside_grace_adopts_and_does_not_dispatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first_dispatch = time.time() - 10
    _layout(tmp_path, first_dispatch)
    calls, fake_run = _gh(existing_run_at=first_dispatch + 5)
    with mock.patch.object(intake_dispatcher.subprocess, "run", side_effect=fake_run), \
         mock.patch.object(intake_dispatcher.time, "sleep", lambda s: None):
        queue_processor.process_queue()
    assert [c for c in calls if c[:3] == ["gh", "workflow", "run"]] == []
    state = json.loads((tmp_path / "central_state.json").read_text())
    task = state["tasks"][intake_dispatcher.fingerprint_task_id(INTAKE)]
    assert task["admission"] == intake_dispatcher.ADMISSION_ADMITTED and task["execution_ref"] == "777"
