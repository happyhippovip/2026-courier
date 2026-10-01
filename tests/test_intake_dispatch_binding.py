"""M05-Q1: intake dispatch must never bind a foreign execution_ref.

Serial case binds the single new run; concurrent/stale/gh-failure cases
fail closed to DISPATCHED_UNBOUND instead of a take-latest run ID.
"""
import json
import os
import subprocess
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
)

from unittest import mock

import intake_dispatcher


def _list_result(runs):
    proc = mock.Mock()
    proc.stdout = json.dumps(runs)
    proc.returncode = 0
    return proc


def _run_after(start, rid):
    return {
        "databaseId": rid,
        "createdAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(start + 5)
        ),
    }


def test_resolve_binds_single_new_run():
    start = time.time()
    with mock.patch.object(
        intake_dispatcher.subprocess,
        "run",
        return_value=_list_result(
            [
                {"databaseId": "111", "createdAt": "2020-01-01T00:00:00Z"},
                _run_after(start, "222"),
            ]
        ),
    ):
        assert (
            intake_dispatcher.resolve_execution_ref("revenue_v1_baseline.yml", start)
            == "222"
        )


def test_resolve_concurrent_runs_returns_none():
    start = time.time()
    with mock.patch.object(
        intake_dispatcher.subprocess,
        "run",
        return_value=_list_result([_run_after(start, "222"), _run_after(start, "333")]),
    ), mock.patch.object(intake_dispatcher.time, "sleep"):
        assert (
            intake_dispatcher.resolve_execution_ref("revenue_v1_baseline.yml", start)
            is None
        )


def test_resolve_stale_only_returns_none():
    start = time.time()
    with mock.patch.object(
        intake_dispatcher.subprocess,
        "run",
        return_value=_list_result(
            [{"databaseId": "111", "createdAt": "2020-01-01T00:00:00Z"}]
        ),
    ), mock.patch.object(intake_dispatcher.time, "sleep"):
        assert (
            intake_dispatcher.resolve_execution_ref("revenue_v1_baseline.yml", start)
            is None
        )


def _dispatch_with_list_runs(tmp_path, monkeypatch, list_runs):
    intake = tmp_path / "in.json"
    intake.write_text(
        json.dumps(
            {
                "customer_reference": "cust-1",
                "target_owner": "o",
                "target_repo": "r",
                "target_sha": "s",
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    ok = mock.Mock()
    ok.returncode = 0
    ok.stdout = ""
    ok.stderr = ""

    def fake_run(cmd, **kwargs):
        if "workflow" in cmd:
            return ok
        return _list_result(list_runs)

    with mock.patch.object(
        intake_dispatcher.subprocess, "run", side_effect=fake_run
    ), mock.patch.object(intake_dispatcher.time, "sleep"):
        intake_dispatcher.dispatch_intake(str(intake))
    with open(tmp_path / "central_state.json") as f:
        state = json.load(f)
    expected = intake_dispatcher.fingerprint_task_id(
        {
            "customer_reference": "cust-1",
            "target_owner": "o",
            "target_repo": "r",
            "target_sha": "s",
        }
    )
    return state["tasks"][expected]


def test_dispatch_concurrent_never_binds_foreign_id(tmp_path, monkeypatch):
    start = time.time()
    task = _dispatch_with_list_runs(
        tmp_path,
        monkeypatch,
        [_run_after(start, "222"), _run_after(start, "333")],
    )
    assert task["execution_ref"] == "DISPATCHED_UNBOUND"
    assert task["execution_ref"] not in ("222", "333")


def test_dispatch_stale_list_marks_unbound(tmp_path, monkeypatch):
    task = _dispatch_with_list_runs(
        tmp_path,
        monkeypatch,
        [{"databaseId": "111", "createdAt": "2020-01-01T00:00:00Z"}],
    )
    assert task["execution_ref"] == "DISPATCHED_UNBOUND"


def test_dispatch_gh_list_failure_marks_unbound(tmp_path, monkeypatch):
    intake = tmp_path / "in.json"
    intake.write_text(
        json.dumps(
            {
                "customer_reference": "cust-1",
                "target_owner": "o",
                "target_repo": "r",
                "target_sha": "s",
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    ok = mock.Mock()
    ok.returncode = 0
    ok.stdout = ""
    ok.stderr = ""

    def fake_run(cmd, **kwargs):
        if "workflow" in cmd:
            return ok
        raise subprocess.CalledProcessError(1, cmd, stderr="boom")

    with mock.patch.object(
        intake_dispatcher.subprocess, "run", side_effect=fake_run
    ), mock.patch.object(intake_dispatcher.time, "sleep"):
        intake_dispatcher.dispatch_intake(str(intake))
    with open(tmp_path / "central_state.json") as f:
        state = json.load(f)
    expected = intake_dispatcher.fingerprint_task_id(
        {
            "customer_reference": "cust-1",
            "target_owner": "o",
            "target_repo": "r",
            "target_sha": "s",
        }
    )
    assert state["tasks"][expected]["execution_ref"] == "DISPATCHED_UNBOUND"
