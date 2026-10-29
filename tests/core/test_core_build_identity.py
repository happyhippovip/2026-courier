"""Test hardening for courier_core.build (build identity + seq attribution).

Tests only; no behavior change. courier_core.build answers "which controller
build wrote this lifecycle": CONTROLLER_STARTED carries build_identity(), and
build_for_seq() attributes every event to the nearest preceding
CONTROLLER_STARTED. This is attribution, not provenance.
"""

from __future__ import annotations

import hashlib
import platform
import re

import pytest

import courier_core
from courier_core import build as build_mod
from courier_core.build import BUILD_ID_ENV, build_for_seq, build_identity, source_sha256
from courier_core.events import Event, EventType


@pytest.fixture(autouse=True)
def _fresh_source_digest():
    build_mod.source_sha256.cache_clear()
    yield
    build_mod.source_sha256.cache_clear()


def _started(seq, build, **extra):
    return Event(type=EventType.CONTROLLER_STARTED, payload={"build": build, **extra}, seq=seq)


def _task_created(seq, task_id="t1"):
    return Event(
        type=EventType.TASK_CREATED,
        task_id=task_id,
        payload={"adapter": "synthetic", "params": {}, "effect_class": "idempotent",
                 "max_attempts": 3, "lease_ttl_s": 6},
        seq=seq,
    )


# ---------------------------------------------------------------- identity

def test_identity_keys_and_version(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    identity = build_identity()
    assert set(identity) == {"version", "build_id", "source_sha256", "python"}
    assert identity["version"] == courier_core.__version__
    assert identity["python"] == platform.python_version()


def test_identity_no_build_id_when_env_unset(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    assert build_identity()["build_id"] is None


def test_identity_empty_build_id_is_none(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "")
    assert build_identity()["build_id"] is None


def test_identity_build_id_passthrough(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "launcher-42")
    assert build_identity()["build_id"] == "launcher-42"


def test_identity_build_id_truncated_to_200(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "b" * 500)
    build_id = build_identity()["build_id"]
    assert build_id == "b" * 200
    assert len(build_id) <= 200


def test_source_sha256_is_hex_or_none():
    digest = source_sha256()
    assert digest is None or re.fullmatch(r"[0-9a-f]{64}", digest)


def test_source_sha256_deterministic_and_cached():
    assert source_sha256() == source_sha256()


def test_source_sha256_scheme_over_sorted_py_files(tmp_path, monkeypatch):
    (tmp_path / "b.py").write_bytes(b"print(2)\n")
    (tmp_path / "a.py").write_bytes(b"print(1)\n")
    (tmp_path / "notes.json").write_bytes(b'{"ignored": true}')
    (tmp_path / "__init__.py").write_bytes(b"")
    monkeypatch.setattr(courier_core, "__file__", str(tmp_path / "__init__.py"))
    # Same scheme as documented in courier_core.build: sorted *.py files,
    # each contributing name + NUL + bytes + NUL.
    digest = hashlib.sha256()
    for path in sorted(tmp_path.glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    assert source_sha256() == digest.hexdigest()


def test_source_sha256_ignores_non_py_files(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_bytes(b"print(1)\n")
    (tmp_path / "notes.json").write_bytes(b'{"ignored": true}')
    (tmp_path / "__init__.py").write_bytes(b"")
    monkeypatch.setattr(courier_core, "__file__", str(tmp_path / "__init__.py"))
    digest = hashlib.sha256()
    for path in sorted(tmp_path.glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    assert source_sha256() == digest.hexdigest()


def test_source_sha256_none_when_no_py_files(tmp_path, monkeypatch):
    monkeypatch.setattr(courier_core, "__file__", str(tmp_path / "__init__.py"))
    assert source_sha256() is None


def test_source_sha256_none_on_unreadable_source(tmp_path, monkeypatch):
    from pathlib import Path

    (tmp_path / "broken.py").write_bytes(b"x = 1\n")
    (tmp_path / "__init__.py").write_bytes(b"")
    monkeypatch.setattr(courier_core, "__file__", str(tmp_path / "__init__.py"))
    real_read_bytes = Path.read_bytes

    def _boom(self):
        raise OSError("unreadable")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    try:
        assert source_sha256() is None
    finally:
        monkeypatch.setattr(Path, "read_bytes", real_read_bytes)


# ---------------------------------------------------------------- build_for_seq

def test_build_for_seq_empty_is_none():
    assert build_for_seq([], 10) is None


def test_build_for_seq_no_start_is_none():
    events = [_task_created(1), _task_created(2)]
    assert build_for_seq(events, 2) is None


def test_build_for_seq_single_start_applies_after_it():
    build = {"version": "1", "build_id": None}
    events = [_started(1, build), _task_created(2)]
    assert build_for_seq(events, 1) == build
    assert build_for_seq(events, 2) == build
    assert build_for_seq(events, 0) is None


def test_build_for_seq_latest_start_wins():
    first = {"version": "1", "build_id": "a"}
    second = {"version": "1", "build_id": "b"}
    events = [_started(1, first), _task_created(2), _started(3, second), _task_created(4)]
    assert build_for_seq(events, 2) == first
    assert build_for_seq(events, 3) == second
    assert build_for_seq(events, 4) == second


def test_build_for_seq_ignores_events_past_seq():
    first = {"version": "1", "build_id": "a"}
    second = {"version": "1", "build_id": "b"}
    events = [_started(1, first), _started(5, second)]
    assert build_for_seq(events, 4) == first
    assert build_for_seq(events, 5) == second


def test_build_for_seq_non_start_events_never_change_build():
    build = {"version": "1", "build_id": "a"}
    events = [_started(1, build), _task_created(2), _task_created(3)]
    assert build_for_seq(events, 3) == build


def test_build_for_seq_accepts_any_iterable():
    build = {"version": "1", "build_id": None}
    events = (_e for _e in [_started(1, build)])
    assert build_for_seq(events, 1) == build
