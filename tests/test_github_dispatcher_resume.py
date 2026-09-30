"""Dispatcher resume: never double-spawn, never hot-loop (Wave 4 D1/D7)."""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEAD_PID = 2 ** 30  # never a live pid in tests


class FakeProc:
    def __init__(self, alive=True):
        self.alive = alive

    def poll(self):
        return None if self.alive else 0


@pytest.fixture
def disp(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "courier_github_dispatcher_resume_under_test",
        ROOT / "scripts" / "courier_github_dispatcher.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "DISPATCH_DIR", tmp_path / "dispatch")
    mod.DISPATCH_DIR.mkdir(parents=True, exist_ok=True)
    mod._spawned.clear()
    mod._resume_counts.clear()
    spawns = []
    def fake_popen(cmd):
        spawns.append(cmd)
        return FakeProc(alive=True)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    mod._spawns = spawns
    return mod


def write_packet(disp, name="dispatch-abc123.json", state=None):
    packet = disp.DISPATCH_DIR / name
    packet.write_text("{}")
    if state is not None:
        packet.with_name(packet.stem + ".github-worker-state.json").write_text(
            json.dumps(state) if not isinstance(state, str) else state)
    return packet


def test_skips_posted(disp):
    write_packet(disp, state={"status": "POSTED", "pid": DEAD_PID})
    assert disp.resume_pending() == 0
    assert disp._spawns == []


def test_skips_live_pid(disp):
    # Orphaned-but-running adapter after dispatcher restart: no double-spawn.
    write_packet(disp, state={"status": "WAITING_FOR_WORKER", "pid": os.getpid()})
    assert disp.resume_pending() == 0
    assert disp._spawns == []


def test_respawns_dead_pid(disp):
    write_packet(disp, state={"status": "WAITING_FOR_WORKER", "pid": DEAD_PID})
    assert disp.resume_pending() == 1
    assert len(disp._spawns) == 1


def test_respawn_is_bounded(disp):
    write_packet(disp, state={"status": "WAITING_FOR_WORKER", "pid": DEAD_PID})
    for _ in range(4):
        disp._spawned.clear()  # simulate each respawned adapter dying again
        disp.resume_pending()
    assert len(disp._spawns) == disp.MAX_RESUMES_PER_DISPATCH == 3


def test_skips_live_handle_even_with_dead_pid_in_file(disp):
    packet = write_packet(disp, state={"status": "WAITING_FOR_WORKER", "pid": DEAD_PID})
    disp._spawned[packet.name] = FakeProc(alive=True)
    assert disp.resume_pending() == 0
    assert disp._spawns == []


def test_corrupt_state_respawns_but_bounded(disp):
    write_packet(disp, state="{torn")
    for _ in range(4):
        disp._spawned.clear()
        disp.resume_pending()
    assert len(disp._spawns) == disp.MAX_RESUMES_PER_DISPATCH == 3


def test_missing_dispatch_dir_returns_zero(disp, tmp_path, monkeypatch):
    monkeypatch.setattr(disp, "DISPATCH_DIR", tmp_path / "absent")
    assert disp.resume_pending() == 0
