"""Install-state contract. Pure evidence derivation; no platform scripts and no skips."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest

from courier_core.install_state import (
    CONFIRMATION_FRESHNESS_S,
    CONTROLLER_STALE,
    CONTROLLER_UNCONFIRMED,
    FAILED,
    HEALTHY,
    INSTALLING,
    INSTALLED_UNVERIFIED,
    INTERRUPTED_INSTALL,
    JOURNAL_UNREADABLE,
    MAX_STATE_BYTES,
    NOT_INSTALLED,
    REPAIR_REQUIRED,
    REFUSED_RUNNING_WORKER,
    Evidence,
    InstallJournal,
    JournalUnreadable,
    SecretRejected,
    derive_state,
    reject_secrets,
    status_from_dir,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "courier_core" / "schemas" / "install_status.schema.json").read_text(encoding="utf-8"))
T0 = datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc)
IDENTITY = {"pid": 4242, "start_time": "2026-10-08T03:00:05+00:00", "executable": "Courier.exe"}
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


def _install(journal, version="1.0.0", *, started=0, finished=10):
    begun = journal.begin(
        version, _at(started),
        config_path="config.json",
        runtime_path="runtime",
    )
    assert begun.ok, begun.reason
    phased = journal.phase("files", _at(started + 1))
    assert phased.ok, phased.reason
    done = journal.complete(_at(finished), process_identity=IDENTITY)
    assert done.ok, done.reason
    return done.journal


def _assert_schema(status):
    jsonschema.validate(status, SCHEMA)


def test_first_install(tmp_path):
    journal = InstallJournal(tmp_path)
    assert derive_state(journal.load(), _evidence(), _at(0))["state"] == NOT_INSTALLED
    _install(journal)
    status = status_from_dir(tmp_path, _evidence(), _at(40))
    assert status["state"] == HEALTHY
    assert status["version"] == "1.0.0"
    assert status["reason_code"] is None
    assert status["worker_id"] == "worker-alice"
    _assert_schema(status)
    first = InstallJournal(tmp_path / "fresh")
    started = first.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime")
    repeated = first.begin("1.0.0", _at(50), config_path="config.json", runtime_path="runtime")
    assert repeated.ok and repeated.journal["started_at"] == started.journal["started_at"]
    assert repeated.journal["phases"] == []


def test_reinstall_same_version_keeps_config(tmp_path):
    journal = InstallJournal(tmp_path)
    _install(journal, "1.0.0")
    config = tmp_path / "config.json"
    config.write_text("user-config", encoding="utf-8")
    again = journal.begin("1.0.0", _at(20))
    assert again.ok
    assert again.journal["version"] == "1.0.0"
    assert again.journal["config_path"] == "config.json"
    assert again.journal["previous"] is None
    done = journal.complete(_at(25), process_identity=IDENTITY)
    assert done.journal["phase"] == "complete"
    assert done.journal["version"] == "1.0.0"
    assert config.read_text(encoding="utf-8") == "user-config"


def test_upgrade_keeps_config_and_previous_for_rollback(tmp_path):
    journal = InstallJournal(tmp_path)
    _install(journal, "1.0.0")
    config = tmp_path / "config.json"
    config.write_text("keep-me", encoding="utf-8")
    upgraded = journal.begin("2.0.0", _at(20))
    assert upgraded.ok
    assert upgraded.journal["version"] == "2.0.0"
    assert upgraded.journal["config_path"] == "config.json"
    assert upgraded.journal["previous"]["version"] == "1.0.0"
    journal.phase("files", _at(21))
    done = journal.complete(_at(30), process_identity=IDENTITY)
    assert done.journal["version"] == "2.0.0"
    assert done.journal["previous"]["version"] == "1.0.0"
    assert config.read_text(encoding="utf-8") == "keep-me"
    status = derive_state(done.journal, _evidence(controller_confirmed_at=_at(40)), _at(50))
    assert status["state"] == HEALTHY
    assert status["version"] == "2.0.0"


def test_repair_required_returns_to_healthy(tmp_path):
    journal = InstallJournal(tmp_path)
    completed = _install(journal)
    broken = derive_state(completed, _evidence(runtime_present=False), _at(40))
    assert broken["state"] == REPAIR_REQUIRED
    assert broken["reason_code"] == "MISSING_RUNTIME"
    repair = journal.begin("1.0.0", _at(50))
    assert repair.ok and repair.journal["phase"] == "installing"
    journal.phase("repair", _at(51))
    done = journal.complete(_at(60), process_identity=IDENTITY)
    status = derive_state(done.journal, _evidence(controller_confirmed_at=_at(70)), _at(80))
    assert status["state"] == HEALTHY
    _assert_schema(status)


def test_failed_install(tmp_path):
    journal = InstallJournal(tmp_path)
    journal.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime")
    failed = journal.fail("COPY_FAILED", _at(5))
    assert failed.ok
    repeated = journal.fail("COPY_FAILED", _at(9))
    assert repeated.ok and repeated.journal == failed.journal
    status = derive_state(failed.journal, _evidence(), _at(10))
    assert status["state"] == FAILED
    assert status["reason_code"] == "COPY_FAILED"
    _assert_schema(status)


def test_interrupted_install_between_phases_is_repair(tmp_path):
    journal = InstallJournal(tmp_path)
    journal.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime")
    journal.phase("files", _at(1))
    # Crash before complete: the journal stays installing.
    fresh = derive_state(journal.load(), _evidence(), _at(30), interrupt_timeout_s=60)
    assert fresh["state"] == INSTALLING
    stalled = derive_state(journal.load(), _evidence(), _at(120), interrupt_timeout_s=60)
    assert stalled["state"] == REPAIR_REQUIRED
    assert stalled["reason_code"] == INTERRUPTED_INSTALL
    _assert_schema(stalled)


def test_rollback_restores_previous_version_marker(tmp_path):
    journal = InstallJournal(tmp_path)
    _install(journal, "1.0.0", finished=10)
    journal.begin("2.0.0", _at(20))
    journal.phase("files", _at(21))
    rolled = journal.rollback(_at(25))
    assert rolled.ok, rolled.reason
    assert rolled.journal["version"] == "1.0.0"
    assert rolled.journal["phase"] == "complete"
    assert rolled.journal["config_path"] == "config.json"
    assert rolled.journal["rolled_back_from"] == "2.0.0"
    status = derive_state(rolled.journal, _evidence(controller_confirmed_at=_at(30)), _at(40))
    assert status["version"] == "1.0.0"
    assert status["state"] == HEALTHY


def test_uninstall_is_not_installed_and_preserves_protected_dirs(tmp_path):
    journal = InstallJournal(tmp_path)
    _install(journal)
    projects = tmp_path / "projects"
    data = tmp_path / "data"
    projects.mkdir()
    data.mkdir()
    (projects / "notes.txt").write_text("project", encoding="utf-8")
    (data / "db").write_text("data", encoding="utf-8")
    removed = journal.uninstall(_at(50))
    assert removed.ok
    assert removed.journal["phase"] == "uninstalled"
    assert (projects / "notes.txt").read_text(encoding="utf-8") == "project"
    assert (data / "db").read_text(encoding="utf-8") == "data"
    status = derive_state(removed.journal, _evidence(), _at(60))
    assert status["state"] == NOT_INSTALLED
    _assert_schema(status)


def test_refuse_install_over_unattributable_running_worker(tmp_path):
    journal = InstallJournal(tmp_path)
    running = {"alive": True, "pid": 99, "start_time": "2026-10-08T03:00:01+00:00", "executable": "other.exe"}
    refused = journal.begin(
        "1.0.0", _at(0), running_worker=running, config_path="config.json", runtime_path="runtime",
    )
    assert refused.ok is False
    assert refused.reason == REFUSED_RUNNING_WORKER
    assert not journal.path.exists()
    _install(journal)
    before = journal.path.read_text(encoding="utf-8")
    again = journal.begin("2.0.0", _at(30), running_worker=running)
    assert again.ok is False and again.reason == REFUSED_RUNNING_WORKER
    assert journal.path.read_text(encoding="utf-8") == before
    owned = dict(IDENTITY, alive=True)
    allowed = journal.begin("2.0.0", _at(30), running_worker=owned)
    assert allowed.ok, allowed.reason


def test_secret_redaction(tmp_path):
    with pytest.raises(SecretRejected):
        reject_secrets({"api_key": SECRET})
    with pytest.raises(SecretRejected):
        reject_secrets({"note": BEARER})
    with pytest.raises(SecretRejected):
        reject_secrets({"nested": [{"password": SECRET}]})
    journal = InstallJournal(tmp_path)
    journal.begin("1.0.0", _at(0), config_path="config.json", runtime_path="runtime")
    journal.phase("note", _at(1), detail={"api_key": SECRET, "note": BEARER, "step": "files"})
    raw = journal.path.read_text(encoding="utf-8")
    assert SECRET not in raw
    assert "super-token-value-should-not-leak" not in raw
    assert BEARER not in raw
    loaded = journal.load()
    reject_secrets(loaded)
    assert loaded["phases"][-1]["detail"]["api_key"] == "[redacted]"
    assert loaded["phases"][-1]["detail"]["note"] == "[redacted]"
    assert loaded["phases"][-1]["detail"]["step"] == "files"
    assert list(tmp_path.glob("*.tmp")) == []


def test_process_alive_but_unregistered_stays_unverified(tmp_path):
    journal = InstallJournal(tmp_path)
    completed = _install(journal)
    status = derive_state(completed, _evidence(controller_worker_id=None, controller_confirmed_at=None), _at(40))
    assert status["state"] == INSTALLED_UNVERIFIED
    assert status["reason_code"] == CONTROLLER_UNCONFIRMED
    assert status["state"] != HEALTHY
    _assert_schema(status)


def test_stale_controller_confirmation_is_not_healthy(tmp_path):
    journal = InstallJournal(tmp_path)
    completed = _install(journal, finished=10)
    stale = derive_state(
        completed,
        _evidence(controller_confirmed_at=_at(11)),
        _at(11 + CONFIRMATION_FRESHNESS_S + 5),
    )
    assert stale["state"] == INSTALLED_UNVERIFIED
    assert stale["reason_code"] == CONTROLLER_STALE
    assert stale["state"] != HEALTHY
    not_newer = derive_state(completed, _evidence(controller_confirmed_at=_at(10)), _at(40))
    assert not_newer["state"] != HEALTHY
    assert not_newer["reason_code"] == CONTROLLER_STALE
    _assert_schema(stale)


def test_privileged_scheduler_is_not_healthy(tmp_path):
    journal = InstallJournal(tmp_path)
    completed = _install(journal)
    status = derive_state(completed, _evidence(scheduler_principal="SYSTEM"), _at(40))
    assert status["state"] == REPAIR_REQUIRED
    assert status["reason_code"] == "SCHEDULER_PRIVILEGED_PRINCIPAL"


def _bound_open(monkeypatch):
    """Count bytes returned by file reads and refuse an unbounded read."""
    read_bytes = {"n": 0}
    real_open = Path.open

    def wrapped(self, mode="r", *args, **kwargs):
        handle = real_open(self, mode, *args, **kwargs)
        original = handle.read

        def read(n=-1):
            if n is None or n < 0 or n > MAX_STATE_BYTES + 1:
                raise AssertionError(f"read beyond cap: {n}")
            data = original(n)
            size = len(data.encode("utf-8")) if isinstance(data, str) else len(data)
            read_bytes["n"] += size
            if read_bytes["n"] > MAX_STATE_BYTES + 1:
                raise AssertionError(f"loaded {read_bytes['n']} bytes")
            return data

        handle.read = read
        return handle

    monkeypatch.setattr(Path, "open", wrapped)
    return read_bytes


def test_oversized_journal_is_unreadable_without_loading_it(tmp_path, monkeypatch):
    path = tmp_path / "install_journal.json"
    with path.open("wb") as handle:
        handle.truncate(MAX_STATE_BYTES + (8 * 1024 * 1024))
    read_bytes = _bound_open(monkeypatch)
    with pytest.raises(JournalUnreadable) as raised:
        InstallJournal(tmp_path).load()
    assert read_bytes["n"] <= MAX_STATE_BYTES + 1
    assert str(tmp_path) not in str(raised.value)
    status = status_from_dir(tmp_path, _evidence(), _at(40))
    assert status["state"] != HEALTHY
    assert status["reason_code"] == JOURNAL_UNREADABLE
    rendered = json.dumps(status)
    assert str(tmp_path) not in rendered
    assert "Traceback" not in rendered
    _assert_schema(status)


def test_journal_exactly_at_cap_still_loads(tmp_path):
    body = b'{"phase":"uninstalled","schema_version":"1"}'
    pad = MAX_STATE_BYTES - len(body)
    assert pad > 0
    raw = body[:-1] + (b" " * pad) + b"}"
    assert len(raw) == MAX_STATE_BYTES
    (tmp_path / "install_journal.json").write_bytes(raw)
    loaded = InstallJournal(tmp_path).load()
    assert loaded["phase"] == "uninstalled"
    assert loaded["schema_version"] == "1"
    status = status_from_dir(tmp_path, _evidence(), _at(40))
    assert status["state"] == NOT_INSTALLED
    assert status["state"] != HEALTHY
