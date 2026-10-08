"""P9 test hardening for courier_core.build (identity + seq attribution).

Tests only; no behavior change. Covers build_identity() (version, build-id
env handling, source digest, python version) and build_for_seq()
(attribution of a journal stream to the nearest preceding
CONTROLLER_STARTED build).
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


def _stopped(seq):
    return Event(type=EventType.CONTROLLER_STOPPED, payload={}, seq=seq)


def test_identity_has_expected_keys_and_version():
    ident = build_identity()
    assert set(ident) == {"version", "build_id", "source_sha256", "python"}
    assert ident["version"] == courier_core.__version__


def test_identity_build_id_defaults_to_none(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    assert build_identity()["build_id"] is None


def test_identity_uses_env_build_id(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "launcher-123")
    assert build_identity()["build_id"] == "launcher-123"


def test_identity_truncates_long_build_id(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "x" * (MAX_BUILD_ID_LENGTH + 50))
    build_id = build_identity()["build_id"]
    assert len(build_id) == MAX_BUILD_ID_LENGTH


def test_identity_python_version_shape():
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", build_identity()["python"])


def test_identity_source_digest_matches_helper():
    assert build_identity()["source_sha256"] == source_sha256()


def test_source_sha256_is_stable_hex_or_none():
    first = source_sha256()
    assert first is None or re.fullmatch(r"[0-9a-f]{64}", first)
    assert source_sha256() == first


def test_source_sha256_none_when_sources_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(courier_core, "__file__", str(tmp_path / "missing" / "mod.py"))
    assert source_sha256() is None


def test_for_seq_empty_stream_is_none():
    assert build_for_seq([], 10) is None


def test_for_seq_without_started_is_none():
    assert build_for_seq([_stopped(1), _stopped(2)], 5) is None


def test_for_seq_picks_last_started_at_or_before():
    build_a = {"version": "a"}
    build_b = {"version": "b"}
    events = [_started(1, build_a), _stopped(2), _started(5, build_b), _stopped(6)]
    assert build_for_seq(events, 6) == build_b
    assert build_for_seq(events, 5) == build_b
    assert build_for_seq(events, 4) == build_a
    assert build_for_seq(events, 0) is None


def test_for_seq_ignores_events_after_seq():
    events = [_started(1, {"version": "a"}), _started(9, {"version": "b"})]
    assert build_for_seq(events, 5) == {"version": "a"}


def test_for_seq_unsequenced_started_events_are_read():
    events = [_started(1, {"version": "a"}), _started(None, {"version": "b"})]
    assert build_for_seq(events, 5) == {"version": "b"}


def test_for_seq_started_without_build_resets_to_none():
    events = [_started(1, {"version": "a"}), Event(type=EventType.CONTROLLER_STARTED, payload={}, seq=2)]
    assert build_for_seq(events, 5) is None


def test_for_seq_ignores_build_key_on_other_event_types():
    events = [Event(type=EventType.CONTROLLER_STOPPED, payload={"build": {"version": "x"}}, seq=3)]
    assert build_for_seq(events, 5) is None
