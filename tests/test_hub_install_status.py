"""Hub installation cards come only from the install-state contract."""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from courier_core.install_state import Evidence, InstallJournal
from courier_hub import model
from courier_hub.cli import install_status_text

T0 = datetime(2026, 10, 8, 4, 0, tzinfo=timezone.utc)
IDENTITY = {"pid": 4242, "start_time": "2026-10-08T04:00:05+00:00", "executable": "Courier.exe"}
SECRET = "super-secret-value-should-not-leak"
BEARER = "Bearer super-token-value-should-not-leak"


def _at(seconds):
    return T0 + timedelta(seconds=seconds)


def _evidence(**overrides):
    base = dict(
        config_present=True,
        runtime_present=True,
        scheduler_registered=True,
        scheduler_principal="alice",
        current_user="alice",
        process_alive=True,
        process_identity=dict(IDENTITY),
        controller_worker_id="worker-alice",
        controller_confirmed_at=_at(30),
    )
    base.update(overrides)
    return Evidence(**base)


def _completed(tmp_path, *, version="1.0.0", finished=10):
    journal = InstallJournal(tmp_path)
    begun = journal.begin(version, _at(0), config_path="config.json", runtime_path="runtime")
    assert begun.ok, begun.reason
    done = journal.complete(_at(finished), process_identity=IDENTITY)
    assert done.ok, done.reason
    return done


def test_healthy_only_with_controller_confirmation(tmp_path):
    _completed(tmp_path)
    healthy = model.host_installation(tmp_path, _evidence(), _at(40), host_id="host-a")
    assert healthy["bucket"] == "working"
    assert healthy["tone"] == "ok"
    assert healthy["contract_state"] == "HEALTHY"
    unverified = model.host_installation(
        tmp_path, _evidence(controller_worker_id=None, controller_confirmed_at=None), _at(40), host_id="host-a",
    )
    assert unverified["bucket"] == "unverified"
    assert unverified["tone"] != "ok"
    assert unverified["bucket"] != "working"


def test_process_alive_but_unregistered_shows_unverified(tmp_path):
    _completed(tmp_path)
    card = model.host_installation(
        tmp_path,
        _evidence(controller_worker_id=None, controller_confirmed_at=None),
        _at(40),
        host_id="host-a",
    )
    assert card["bucket"] == "unverified"
    assert card["tone"] != "ok"
    assert "installed successfully" not in json.dumps(card).lower()


def test_failed_and_repair_show_needs_human_with_reason(tmp_path):
    failed_dir = tmp_path / "failed"
    journal = InstallJournal(failed_dir)
    assert journal.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime").ok
    assert journal.fail("COPY_FAILED", _at(5)).ok
    failed = model.host_installation(failed_dir, _evidence(), _at(40), host_id="host-a")
    assert failed["bucket"] == "needs_human"
    assert failed["reason_code"] == "COPY_FAILED"
    assert failed["tone"] != "ok"

    repair_dir = tmp_path / "repair"
    _completed(repair_dir)
    repair = model.host_installation(repair_dir, _evidence(runtime_present=False), _at(40), host_id="host-a")
    assert repair["bucket"] == "needs_human"
    assert repair["reason_code"] == "MISSING_RUNTIME"
    assert repair["tone"] != "ok"


def test_corrupt_status_file_shows_unknown_never_healthy(tmp_path):
    (tmp_path / "install_journal.json").write_text("{not json", encoding="utf-8")
    card = model.host_installation(tmp_path, _evidence(), _at(40), host_id="host-a")
    assert card["bucket"] == "unknown"
    assert card["tone"] != "ok"
    assert card["bucket"] != "working"
    assert card["contract_state"] != "HEALTHY"
    missing = model.host_installation(tmp_path / "absent", _evidence(), _at(40), host_id="host-a")
    assert missing["bucket"] == "unknown"
    assert missing["tone"] != "ok"


def test_installing_and_not_installed_are_not_healthy(tmp_path):
    installing = tmp_path / "installing"
    journal = InstallJournal(installing)
    assert journal.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime").ok
    card = model.host_installation(installing, _evidence(), _at(5), host_id="host-a")
    assert card["bucket"] == "in_progress"
    assert card["tone"] != "ok"
    removed = tmp_path / "removed"
    done = InstallJournal(removed)
    assert done.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime").ok
    assert done.complete(_at(10), process_identity=IDENTITY).ok
    assert done.uninstall(_at(20)).ok
    gone = model.host_installation(removed, _evidence(), _at(30), host_id="host-a")
    assert gone["bucket"] == "not_installed"
    assert gone["tone"] != "ok"


def test_unreadable_install_dir_is_unknown_without_traceback(tmp_path, capsys):
    """A directory the customer cannot read is unknown. It must not raise, and the
    private path must not appear in the card or the command output."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "install_journal.json").write_text("{not json", encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text("{}", encoding="utf-8")
    os.chmod(state, 0)
    try:
        card = model.host_installation(state, _evidence(), _at(40), host_id="host-a")
        rendered = json.dumps(card)
        assert card["bucket"] == "unknown"
        assert card["tone"] != "ok"
        assert card["bucket"] != "working"
        assert card["contract_state"] != "HEALTHY"
        assert card["reason_code"] == "STATUS_UNREADABLE"
        assert str(tmp_path) not in rendered
        assert "Traceback" not in rendered

        from courier_hub.cli import main

        code = main(["courier-hub", "install-status", "--state-dir", str(state),
                     "--evidence", str(evidence_path), "--now", _at(40).isoformat(), "--host", "host-a"])
        captured = capsys.readouterr()
        assert code == 0
        assert "Traceback" not in captured.out
        assert "Traceback" not in captured.err
        assert str(tmp_path) not in captured.out
        assert str(tmp_path) not in captured.err
        body = json.loads(captured.out)
        assert body["bucket"] == "unknown"
        assert body["tone"] != "ok"
        assert body["reason_code"] == "STATUS_UNREADABLE"
    finally:
        os.chmod(state, 0o755)


def test_secret_values_never_appear_in_model_or_cli_output(tmp_path, capsys):
    journal = InstallJournal(tmp_path)
    assert journal.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime").ok
    journal.phase("note", _at(1), detail={"api_key": SECRET, "note": BEARER})
    assert journal.complete(_at(10), process_identity=IDENTITY).ok
    evidence = _evidence(controller_worker_id=BEARER)
    card = model.host_installation(tmp_path, evidence, _at(40), host_id="host-a")
    rendered = json.dumps(card)
    assert SECRET not in rendered
    assert "super-token-value-should-not-leak" not in rendered
    text = install_status_text(tmp_path, evidence, _at(40), host_id="host-a")
    assert SECRET not in text
    assert "super-token-value-should-not-leak" not in text
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps({
        "config_present": True,
        "runtime_present": True,
        "scheduler_registered": True,
        "scheduler_principal": "alice",
        "current_user": "alice",
        "process_alive": True,
        "process_identity": IDENTITY,
        "controller_worker_id": "worker-alice",
        "controller_confirmed_at": _at(30).isoformat(),
        "api_key": SECRET,
        "note": BEARER,
    }), encoding="utf-8")
    from courier_hub.cli import main
    code = main(["courier-hub", "install-status", "--state-dir", str(tmp_path),
                 "--evidence", str(evidence_path), "--now", _at(40).isoformat(), "--host", "host-a"])
    assert code == 0
    captured = capsys.readouterr().out
    assert SECRET not in captured
    assert "super-token-value-should-not-leak" not in captured
    assert json.loads(captured)["bucket"] == "working"
