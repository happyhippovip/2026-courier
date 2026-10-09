"""P9 hardening for courier_core.build (for-seq edge pins, tests only).

No behavior change. Covers build_identity env truncation, source_sha256
shape/determinism, and build_for_seq boundary/selectivity edges offline.
"""

from __future__ import annotations

import platform
import re

import pytest

import courier_core
from courier_core import build as build_mod
from courier_core.build import build_for_seq, build_identity, source_sha256
from courier_core.events import Event, EventType


@pytest.fixture(autouse=True)
def _clear_source_cache():
    build_mod.source_sha256.cache_clear()
    yield
    build_mod.source_sha256.cache_clear()


def _started(build, seq=None):
    return Event(type=EventType.CONTROLLER_STARTED, payload={"build": build}, seq=seq)


def _other(seq=None):
    return Event(type=EventType.CONTROLLER_STOPPED, payload={}, seq=seq)


def test_source_sha256_is_hex_and_deterministic():
    first = source_sha256()
    assert first is None or re.fullmatch(r"[0-9a-f]{64}", first)
    assert source_sha256() == first


def test_source_sha256_cached_singleton():
    # lru_cache(maxsize=1): repeated calls return the same value without recompute.
    assert source_sha256() == source_sha256()
    assert build_mod.source_sha256.cache_info().maxsize == 1


def test_build_identity_shape_and_version():
    ident = build_identity()
    assert set(ident) == {"version", "build_id", "source_sha256", "python"}
    assert ident["version"] == courier_core.__version__
    assert ident["python"] == platform.python_version()
    assert ident["source_sha256"] == source_sha256()


def test_build_identity_no_env_gives_none_build_id(monkeypatch):
    monkeypatch.delenv(build_mod.BUILD_ID_ENV, raising=False)
    assert build_identity()["build_id"] is None


def test_build_identity_empty_env_gives_none(monkeypatch):
    monkeypatch.setenv(build_mod.BUILD_ID_ENV, "")
    assert build_identity()["build_id"] is None


def test_build_identity_short_id_preserved(monkeypatch):
    monkeypatch.setenv(build_mod.BUILD_ID_ENV, "abc-123")
    assert build_identity()["build_id"] == "abc-123"


def test_build_identity_truncates_to_200(monkeypatch):
    monkeypatch.setenv(build_mod.BUILD_ID_ENV, "x" * 500)
    got = build_identity()["build_id"]
    assert got == "x" * build_mod.MAX_BUILD_ID_LENGTH
    assert len(got) == 200


def test_build_identity_exact_200_preserved(monkeypatch):
    monkeypatch.setenv(build_mod.BUILD_ID_ENV, "y" * 200)
    assert build_identity()["build_id"] == "y" * 200


def test_build_for_seq_empty_is_none():
    assert build_for_seq([], 1) is None


def test_build_for_seq_no_started_is_none():
    assert build_for_seq([_other(seq=1), _other(seq=2)], 5) is None


def test_build_for_seq_single_started_before_seq():
    marker = {"version": "v", "n": 1}
    assert build_for_seq([_started(marker, seq=2)], 5) == marker


def test_build_for_seq_started_after_seq_ignored():
    marker = {"version": "v"}
    assert build_for_seq([_started(marker, seq=9)], 5) is None


def test_build_for_seq_boundary_inclusive():
    marker = {"version": "v"}
    assert build_for_seq([_started(marker, seq=5)], 5) == marker


def test_build_for_seq_last_started_wins():
    first = {"n": 1}
    second = {"n": 2}
    events = [_started(first, seq=1), _started(second, seq=3)]
    assert build_for_seq(events, 5) == second


def test_build_for_seq_later_started_beyond_seq_does_not_override():
    first = {"n": 1}
    second = {"n": 2}
    events = [_started(first, seq=1), _started(second, seq=9)]
    assert build_for_seq(events, 5) == first


def test_build_for_seq_ignores_non_started_between():
    marker = {"n": 7}
    events = [_started(marker, seq=1), _other(seq=2), _other(seq=3)]
    assert build_for_seq(events, 5) == marker


def test_build_for_seq_seq_none_events_are_considered():
    # seq=None never triggers the early break, so a STARTED without seq counts.
    marker = {"n": "none-seq"}
    assert build_for_seq([_started(marker)], 1) == marker


def test_build_for_seq_missing_build_key_gives_none():
    assert build_for_seq([_started(None, seq=1)], 5) is None
    ev = Event(type=EventType.CONTROLLER_STARTED, payload={}, seq=1)
    assert build_for_seq([ev], 5) is None
