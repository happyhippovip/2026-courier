"""Repair restores a damaged install and reports HEALTHY only after the contract agrees.

No platform installer is invoked. File restore uses the temp directory. Scheduler
registration and process start are injected so this does not claim a native
Windows service proof.
"""

from datetime import timedelta
from pathlib import Path

from courier_core.install_repair import repair
from courier_core.install_state import (
    FAILED,
    HEALTHY,
    REPAIR_REQUIRED,
    Evidence,
    InstallJournal,
    status_from_dir,
)


T0 = __import__("datetime").datetime(2026, 10, 8, 4, 0, tzinfo=__import__("datetime").timezone.utc)
IDENTITY = {"pid": 4242, "start_time": "2026-10-08T04:00:05+00:00", "executable": "Courier.exe"}


def _at(seconds):
    return T0 + timedelta(seconds=seconds)


def _completed(state, version="1.0.0"):
    journal = InstallJournal(state)
    begun = journal.begin(version, _at(0), config_path="config.json", runtime_path="runtime")
    assert begun.ok, begun.reason
    assert journal.phase("files", _at(1)).ok
    done = journal.complete(_at(10), process_identity=IDENTITY)
    assert done.ok, done.reason
    (state / "config.json").write_text("user-config", encoding="utf-8")
    (state / "runtime").write_text("runtime-bytes", encoding="utf-8")
    data = state / "data"
    data.mkdir()
    (data / "note.txt").write_text("keep-me", encoding="utf-8")
    return journal


def _world(state):
    world = {"registered": True, "started": True, "calls": []}

    def observe():
        alive = world["started"]
        return Evidence(
            config_present=(state / "config.json").is_file(),
            runtime_present=(state / "runtime").is_file(),
            scheduler_registered=world["registered"],
            scheduler_principal="alice" if world["registered"] else None,
            current_user="alice",
            process_alive=alive,
            process_identity=dict(IDENTITY) if alive else None,
            controller_worker_id="worker-alice" if alive else None,
            controller_confirmed_at=_at(80) if alive else None,
        )

    def register():
        world["calls"].append("register")
        world["registered"] = True
        return True

    def start():
        world["calls"].append("start")
        world["started"] = True
        return dict(IDENTITY)

    return world, observe, register, start


def test_damaged_runtime_is_restored_and_healthy_only_after_verification(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    _completed(state)
    (state / "runtime").unlink()
    package = tmp_path / "package"
    package.mkdir()
    (package / "runtime").write_text("runtime-bytes", encoding="utf-8")
    (package / "Courier.exe").write_text("launcher-bytes", encoding="utf-8")
    world, observe, register, start = _world(state)
    world["registered"] = False
    world["started"] = False

    result = repair(
        state, _at(90), package_dir=package, observe=observe, register=register, start=start,
        launcher_path="Courier.exe",
    )

    assert result["state"] == HEALTHY
    assert result["reported"] == HEALTHY
    assert result["noop"] is False
    assert (state / "runtime").read_text(encoding="utf-8") == "runtime-bytes"
    assert (state / "Courier.exe").read_text(encoding="utf-8") == "launcher-bytes"
    assert (state / "config.json").read_text(encoding="utf-8") == "user-config"
    assert (state / "data" / "note.txt").read_text(encoding="utf-8") == "keep-me"
    assert world["calls"] == ["register", "start"]
    journal = InstallJournal(state).load()
    assert [item["name"] for item in journal["phases"]][-6:] == [
        "PREFLIGHT", "INSTALL", "CONFIGURE", "CONNECT", "VERIFY", "START",
    ]


def test_second_repair_of_a_healthy_install_is_a_noop(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    _completed(state)
    package = tmp_path / "package"
    package.mkdir()
    (package / "runtime").write_text("other-bytes", encoding="utf-8")
    world, observe, register, start = _world(state)
    before = (state / "install_journal.json").read_bytes()

    first = repair(
        state, _at(90), package_dir=package, observe=observe, register=register, start=start,
    )
    after_first = (state / "install_journal.json").read_bytes()
    second = repair(
        state, _at(100), package_dir=package, observe=observe, register=register, start=start,
    )

    assert first["state"] == HEALTHY and first["noop"] is True
    assert second["state"] == HEALTHY and second["noop"] is True and second["reported"] == HEALTHY
    assert after_first == before
    assert (state / "install_journal.json").read_bytes() == before
    assert world["calls"] == []
    assert (state / "runtime").read_text(encoding="utf-8") == "runtime-bytes"
    assert (state / "data" / "note.txt").read_text(encoding="utf-8") == "keep-me"


def test_repair_failure_is_not_healthy_and_rollback_restores_the_previous_marker(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    journal = _completed(state)
    (state / "runtime").unlink()
    package = tmp_path / "package"
    package.mkdir()
    world, observe, register, start = _world(state)
    world["registered"] = False

    result = repair(
        state, _at(90), package_dir=package, observe=observe, register=register, start=start,
    )

    assert result["state"] == FAILED
    assert result["reported"] != HEALTHY
    assert result["state"] != HEALTHY
    saved = InstallJournal(state).load()
    assert saved["previous"]["version"] == "1.0.0"
    assert (state / "config.json").read_text(encoding="utf-8") == "user-config"
    assert (state / "data" / "note.txt").read_text(encoding="utf-8") == "keep-me"
    rolled = journal.rollback(_at(120))
    assert rolled.ok, rolled.reason
    assert rolled.journal["version"] == "1.0.0"
    assert rolled.journal["phase"] == "complete"
    status = status_from_dir(state, observe(), _at(130))
    assert status["state"] == REPAIR_REQUIRED
