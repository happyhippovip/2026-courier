"""P9 gap pins for courier_core.build (tests-only, no behavior change).

Covers build_identity / source_sha256 / build_for_seq pure paths that have
no dedicated test file in the base tree. Offline only: no network, no
credentials, no filesystem writes outside tmp fixtures via monkeypatch.
"""

from __future__ import annotations

import platform
import re

import pytest

import courier_core
from courier_core import build as build_mod
from courier_core.build import build_for_seq, build_identity, source_sha256
from courier_core.events import Event, EventType

HEX64 = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    source_sha256.cache_clear()
    monkeypatch.delenv(build_mod.BUILD_ID_ENV, raising=False)
    yield
    source_sha256.cache_clear()


_MISSING = object()


def _started(seq, build=_MISSING):
    if build is _MISSING:
        payload: dict = {}
    else:
        payload = {"build": build}
    return Event(type=EventType.CONTROLLER_STARTED, payload=payload, seq=seq)


def test_identity_shape_and_version():
    identity = build_identity()
    assert set(identity) == {"version", "build_id", "source_sha256", "python"}
    assert identity["version"] == courier_core.__version__
    assert identity["python"] == platform.python_version()
    assert identity["build_id"] is None
    assert identity["source_sha256"] is None or HEX64.match(identity["source_sha256"])


def test_identity_empty_build_id_is_none(monkeypatch):
    monkeypatch.setenv(build_mod.BUILD_ID_ENV, "")
    assert build_identity()["build_id"] is None


def test_identity_short_build_id_passes_through(monkeypatch):
    monkeypatch.setenv(build_mod.BUILD_ID_ENV, "lane-L6-test-42")
    assert build_identity()["build_id"] == "lane-L6-test-42"


def test_identity_long_build_id_truncated_to_bound(monkeypatch):
    long_id = "b" * (build_mod.MAX_BUILD_ID_LENGTH + 50)
    monkeypatch.setenv(build_mod.BUILD_ID_ENV, long_id)
    got = build_identity()["build_id"]
    assert got == "b" * build_mod.MAX_BUILD_ID_LENGTH
    assert len(got) == build_mod.MAX_BUILD_ID_LENGTH


def test_source_sha256_shape_and_cache():
    first = source_sha256()
    assert first is None or HEX64.match(first)
    assert source_sha256() == first


def test_source_sha256_no_python_files_is_none(monkeypatch):
    import pathlib

    monkeypatch.setattr(pathlib.Path, "glob", lambda self, pattern: [])
    source_sha256.cache_clear()
    assert source_sha256() is None


def test_source_sha256_unreadable_file_is_none(monkeypatch):
    import pathlib
    from unittest.mock import MagicMock

    fake = MagicMock()
    fake.name = "build.py"
    fake.read_bytes.side_effect = OSError("denied")
    monkeypatch.setattr(pathlib.Path, "glob", lambda self, pattern: [fake])
    source_sha256.cache_clear()
    assert source_sha256() is None


def test_build_for_seq_empty_is_none():
    assert build_for_seq([], 1) is None
    assert build_for_seq(iter([]), 99) is None


def test_build_for_seq_ignores_non_started_events():
    from core_builders import created

    assert build_for_seq([created()], 10) is None
    stopped = Event(type=EventType.CONTROLLER_STOPPED, seq=1)
    assert build_for_seq([stopped], 5) is None


def test_build_for_seq_single_started():
    build = {"version": "1.0.0.dev0", "build_id": "x"}
    events = [_started(3, build)]
    assert build_for_seq(events, 3) == build
    assert build_for_seq(events, 99) == build
    assert build_for_seq(events, 2) is None


def test_build_for_seq_last_started_wins():
    first = {"version": "v1"}
    second = {"version": "v2"}
    events = [_started(1, first), _started(4, second)]
    assert build_for_seq(events, 1) == first
    assert build_for_seq(events, 3) == first
    assert build_for_seq(events, 4) == second
    assert build_for_seq(events, 100) == second


def test_build_for_seq_stops_at_first_event_beyond_target():
    build = {"version": "v1"}
    later = {"version": "v2"}
    events = [_started(2, build), _started(9, later)]
    assert build_for_seq(events, 5) == build
    # seq 9 event must not leak into a query for seq 5 even though it is later in the list
    assert build_for_seq(events, 8) == build


def test_build_for_seq_unsequenced_started_counts():
    build = {"version": "v9"}
    events = [_started(None, build)]
    assert build_for_seq(events, 0) == build
    assert build_for_seq(events, 10**9) == build


def test_build_for_seq_started_without_build_key_resets_to_none():
    first = {"version": "v1"}
    events = [_started(1, first), _started(2)]
    assert build_for_seq(events, 1) == first
    assert build_for_seq(events, 2) is None


def test_build_for_seq_accepts_generators():
    build = {"version": "gen"}
    gen = (e for e in [_started(1, build)])
    assert build_for_seq(gen, 1) == build
