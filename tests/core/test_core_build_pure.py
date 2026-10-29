"""P9 hardening for courier_core.build: pure env + cache + seq attribution.

Tests only; no behavior change. No network calls.

Covers build_identity() env handling (absent, empty, truncation),
source_sha256() stability/caching/edge cases, and build_for_seq()
attribution over synthetic Event streams.
"""

import re

import pytest

import courier_core
from courier_core import build as build_mod
from courier_core.build import (
    BUILD_ID_ENV,
    MAX_BUILD_ID_LENGTH,
    build_for_seq,
    build_identity,
    source_sha256,
)
from courier_core.events import Event, EventType


@pytest.fixture(autouse=True)
def _clear_source_cache():
    build_mod.source_sha256.cache_clear()
    yield
    build_mod.source_sha256.cache_clear()


def _started(seq, build):
    return Event(type=EventType.CONTROLLER_STARTED, payload={"build": build}, seq=seq)


def _other(seq):
    return Event(type=EventType.CONTROLLER_STOPPED, payload={}, seq=seq)


# -- build_identity ------------------------------------------------------

def test_pure_identity_has_expected_keys_and_version():
    identity = build_identity()
    assert set(identity) == {"version", "build_id", "source_sha256", "python"}
    assert identity["version"] == courier_core.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", __import__("platform").python_version())
    assert isinstance(identity["python"], str) and identity["python"]


def test_pure_identity_build_id_absent_is_none(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    assert build_identity()["build_id"] is None


def test_pure_identity_empty_env_is_none(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "")
    assert build_identity()["build_id"] is None


def test_pure_identity_valid_env_passthrough(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "lane-build-123")
    assert build_identity()["build_id"] == "lane-build-123"


def test_pure_identity_exact_limit_not_truncated(monkeypatch):
    value = "x" * MAX_BUILD_ID_LENGTH
    assert MAX_BUILD_ID_LENGTH == 200
    monkeypatch.setenv(BUILD_ID_ENV, value)
    assert build_identity()["build_id"] == value


def test_pure_identity_overlong_truncated_to_limit(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "y" * (MAX_BUILD_ID_LENGTH + 1))
    got = build_identity()["build_id"]
    assert got == "y" * MAX_BUILD_ID_LENGTH


def test_pure_identity_source_digest_matches_helper():
    assert build_identity()["source_sha256"] == source_sha256()


# -- source_sha256 -------------------------------------------------------

def test_pure_source_digest_stable_hex_or_none():
    first = source_sha256()
    second = source_sha256()
    assert first == second
    if first is not None:
        assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_pure_source_digest_cached_second_call_no_reread(monkeypatch):
    calls = {"n": 0}
    from pathlib import Path as RealPath

    real_read = RealPath.read_bytes

    def counting(self):
        calls["n"] += 1
        return real_read(self)

    monkeypatch.setattr(RealPath, "read_bytes", counting)
    first = source_sha256()
    n_after_first = calls["n"]
    assert n_after_first > 0
    second = source_sha256()
    assert second == first
    assert calls["n"] == n_after_first


def test_pure_source_digest_none_when_no_py_files(monkeypatch, tmp_path):
    probe = tmp_path / "pkg" / "probe.py"
    probe.parent.mkdir(parents=True)
    probe.write_text("x = 1\n", encoding="utf-8")
    # Point the package at an empty directory: no *.py files -> None.
    empty = tmp_path / "empty"
    empty.mkdir()
    fake_init = empty / "__init__.py"
    fake_init.write_text("", encoding="utf-8")
    monkeypatch.setattr(courier_core, "__file__", str(fake_init))
    # Remove the only .py file so glob finds nothing.
    fake_init.unlink()
    assert source_sha256() is None


def test_pure_source_digest_none_on_read_error(monkeypatch):
    from pathlib import Path as RealPath

    def boom(self):
        raise OSError("unreadable")

    monkeypatch.setattr(RealPath, "read_bytes", boom)
    assert source_sha256() is None


# -- build_for_seq -------------------------------------------------------

def test_pure_for_seq_empty_stream_is_none():
    assert build_for_seq([], 10) is None
    assert build_for_seq(iter([]), 10) is None


def test_pure_for_seq_without_started_is_none():
    assert build_for_seq([_other(1), _other(2)], 5) is None


def test_pure_for_seq_single_start_applies_at_and_after():
    build = {"version": "1", "build_id": None, "source_sha256": None, "python": "3.12.0"}
    events = [_started(3, build), _other(4)]
    assert build_for_seq(events, 2) is None
    assert build_for_seq(events, 3) == build
    assert build_for_seq(events, 4) == build
    assert build_for_seq(events, 999) == build


def test_pure_for_seq_last_started_wins():
    first = {"version": "1", "build_id": "a", "source_sha256": None, "python": "3.12.0"}
    second = {"version": "1", "build_id": "b", "source_sha256": None, "python": "3.12.0"}
    events = [_started(1, first), _other(2), _started(5, second), _other(6)]
    assert build_for_seq(events, 1) == first
    assert build_for_seq(events, 4) == first
    assert build_for_seq(events, 5) == second
    assert build_for_seq(events, 6) == second


def test_pure_for_seq_ignores_events_after_target():
    build = {"version": "1", "build_id": "a", "source_sha256": None, "python": "3.12.0"}
    later = {"version": "1", "build_id": "b", "source_sha256": None, "python": "3.12.0"}
    events = [_started(1, build), _started(10, later)]
    assert build_for_seq(events, 5) == build


def test_pure_for_seq_unsequenced_events_are_read():
    build = {"version": "1", "build_id": "a", "source_sha256": None, "python": "3.12.0"}
    ev = Event(type=EventType.CONTROLLER_STARTED, payload={"build": build}, seq=None)
    assert build_for_seq([ev], 0) == build


def test_pure_for_seq_missing_build_key_resets_to_none():
    build = {"version": "1", "build_id": "a", "source_sha256": None, "python": "3.12.0"}
    events = [_started(1, build), _other(2),
              Event(type=EventType.CONTROLLER_STARTED, payload={}, seq=3)]
    assert build_for_seq(events, 2) == build
    assert build_for_seq(events, 3) is None


def test_pure_for_seq_none_build_value_is_none():
    build = {"version": "1", "build_id": "a", "source_sha256": None, "python": "3.12.0"}
    events = [_started(1, build), _started(2, None)]
    assert build_for_seq(events, 2) is None


def test_pure_for_seq_other_types_never_change_build():
    build = {"version": "1", "build_id": "a", "source_sha256": None, "python": "3.12.0"}
    ev = Event(type=EventType.CONTROLLER_STOPPED, payload={"build": {"version": "X"}},
               seq=2)
    assert build_for_seq([_started(1, build), ev], 2) == build


def test_pure_for_seq_accepts_generator():
    build = {"version": "1", "build_id": "g", "source_sha256": None, "python": "3.12.0"}
    gen = (e for e in [_other(1), _started(2, build)])
    assert build_for_seq(gen, 2) == build
