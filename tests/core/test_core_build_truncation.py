"""P9 hardening pins for courier_core.build (tests only, no behavior change).

Focus: build_identity() build_id truncation at MAX_BUILD_ID_LENGTH and
build_for_seq() attribution (last CONTROLLER_STARTED at or before seq).
Covers courier_core/build.py, which has no dedicated test file on the base.
New file tests/core/test_core_build_truncation.py; no source edits.
"""

import platform

import courier_core
from core_builders import stable
from courier_core import build as build_mod
from courier_core.build import (
    BUILD_ID_ENV,
    MAX_BUILD_ID_LENGTH,
    build_for_seq,
    build_identity,
    source_sha256,
)
from courier_core.events import Event, EventType


def _started(build, seq):
    return Event(**stable(type=EventType.CONTROLLER_STARTED, payload={"build": build}, seq=seq))


def test_identity_keys_and_version_python():
    build_mod.source_sha256.cache_clear()
    try:
        identity = build_identity()
    finally:
        build_mod.source_sha256.cache_clear()
    assert set(identity) == {"version", "build_id", "source_sha256", "python"}
    assert identity["version"] == courier_core.__version__
    assert identity["python"] == platform.python_version()


def test_identity_build_id_missing_is_none(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    build_mod.source_sha256.cache_clear()
    try:
        assert build_identity()["build_id"] is None
    finally:
        build_mod.source_sha256.cache_clear()


def test_identity_build_id_empty_is_none(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "")
    build_mod.source_sha256.cache_clear()
    try:
        assert build_identity()["build_id"] is None
    finally:
        build_mod.source_sha256.cache_clear()


def test_identity_build_id_short_passthrough(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "abc-123")
    build_mod.source_sha256.cache_clear()
    try:
        assert build_identity()["build_id"] == "abc-123"
    finally:
        build_mod.source_sha256.cache_clear()


def test_identity_build_id_truncated_to_max(monkeypatch):
    long_id = "x" * (MAX_BUILD_ID_LENGTH + 50)
    assert MAX_BUILD_ID_LENGTH == 200
    monkeypatch.setenv(BUILD_ID_ENV, long_id)
    build_mod.source_sha256.cache_clear()
    try:
        truncated = build_identity()["build_id"]
    finally:
        build_mod.source_sha256.cache_clear()
    assert truncated == "x" * MAX_BUILD_ID_LENGTH
    assert len(truncated) == MAX_BUILD_ID_LENGTH


def test_source_sha256_shape_or_none():
    build_mod.source_sha256.cache_clear()
    try:
        first = source_sha256()
        second = source_sha256()
    finally:
        build_mod.source_sha256.cache_clear()
    assert first == second
    if first is not None:
        assert len(first) == 64
        int(first, 16)


def test_build_for_seq_empty_is_none():
    assert build_for_seq([], 10) is None


def test_build_for_seq_no_controller_started_is_none():
    events = [Event(**stable(type=EventType.CONTROLLER_STOPPED, seq=1))]
    assert build_for_seq(events, 5) is None


def test_build_for_seq_picks_last_at_or_before_seq():
    b1, b2 = {"v": 1}, {"v": 2}
    events = [_started(b1, 3), _started(b2, 7)]
    assert build_for_seq(events, 2) is None
    assert build_for_seq(events, 3) == b1
    assert build_for_seq(events, 6) == b1
    assert build_for_seq(events, 7) == b2


def test_build_for_seq_ignores_later_builds_after_break():
    b1, b2 = {"v": 1}, {"v": 2}
    events = [_started(b1, 3), _started(b2, 100)]
    assert build_for_seq(events, 10) == b1


def test_build_for_seq_skips_non_started_events():
    build = {"v": 9}
    events = [
        _started(build, 4),
        Event(**stable(type=EventType.CONTROLLER_STOPPED, seq=5)),
    ]
    assert build_for_seq(events, 5) == build


def test_build_for_seq_none_seq_started_counts():
    build = {"v": 5}
    events = [_started(build, None)]
    assert build_for_seq(events, 0) == build


def test_build_for_seq_returns_recorded_object():
    build = {"v": 7}
    event = _started(build, 1)
    found = build_for_seq([event], 1)
    assert found == build
    assert found is event.payload["build"]
