"""P9 hardening for courier_core.build: build_for_seq attribution + identity env.

Tests only; no behavior change. Covers the pure attribution helper
``build_for_seq`` (which CONTROLLER_STARTED build each seq belongs to) and
the ``build_identity`` environment handling (empty vs long COURIER_BUILD_ID).

No network. No credentials. No filesystem writes outside tmp.
"""

from __future__ import annotations

import platform
import re

import courier_core
from courier_core.build import (
    BUILD_ID_ENV,
    MAX_BUILD_ID_LENGTH,
    build_for_seq,
    build_identity,
    source_sha256,
)
from courier_core.events import Event, EventType

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _started(seq: int | None, build) -> Event:
    return Event(type=EventType.CONTROLLER_STARTED, payload={"build": build},
                 seq=None if seq is None else seq)


def _started_no_build_key(seq: int) -> Event:
    return Event(type=EventType.CONTROLLER_STARTED, payload={"note": "no build recorded"}, seq=seq)


def _created(seq: int) -> Event:
    return Event(
        type=EventType.TASK_CREATED,
        task_id="t1",
        payload={
            "adapter": "synthetic",
            "params": {"sleep_s": 1},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 6,
        },
        seq=seq,
    )


# --- build_for_seq: basics ---

def test_empty_history_has_no_build():
    assert build_for_seq([], 1) is None


def test_no_controller_started_has_no_build():
    assert build_for_seq([_created(1), _created(2)], 2) is None


def test_single_build_applies_at_and_after_its_seq():
    build = {"version": "v1"}
    events = [_started(1, build)]
    assert build_for_seq(events, 1) == build
    assert build_for_seq(events, 2) == build
    assert build_for_seq(events, 100) == build


def test_query_before_first_started_has_no_build():
    build = {"version": "v1"}
    assert build_for_seq([_started(5, build)], 4) is None


def test_seq_boundary_is_inclusive():
    build = {"version": "v1"}
    assert build_for_seq([_started(3, build)], 3) == build


def test_events_past_query_seq_are_ignored():
    first = {"version": "first"}
    second = {"version": "second"}
    events = [_started(1, first), _started(5, second)]
    assert build_for_seq(events, 3) == first
    assert build_for_seq(events, 5) == second


def test_last_started_at_or_before_seq_wins():
    builds = [{"n": i} for i in range(3)]
    events = [_started(1, builds[0]), _started(2, builds[1]), _started(3, builds[2])]
    assert build_for_seq(events, 2) == builds[1]
    assert build_for_seq(events, 3) == builds[2]


def test_non_started_events_do_not_change_attribution():
    build = {"version": "v1"}
    events = [_started(1, build), _created(2), _created(3)]
    assert build_for_seq(events, 3) == build


def test_started_without_build_key_resets_to_none():
    build = {"version": "v1"}
    events = [_started(1, build), _started_no_build_key(2)]
    assert build_for_seq(events, 1) == build
    assert build_for_seq(events, 2) is None


def test_unsequenced_started_events_count():
    build = {"version": "v1"}
    assert build_for_seq([_started(None, build)], 1) == build


def test_unsequenced_non_started_events_do_not_stop_scan():
    build = {"version": "v1"}
    events = [Event(type=EventType.CONTROLLER_STARTED, payload={"build": build}),
              _created(5)]
    assert build_for_seq(events, 5) == build


def test_accepts_any_iterable_not_only_lists():
    build = {"version": "v1"}
    events = (_started(seq, build if seq == 2 else {"other": True}) for seq in (1, 2))
    assert build_for_seq(events, 2) == build


def test_returns_payload_build_object_as_recorded():
    build = {"version": "v1", "build_id": None}
    events = [_started(7, build)]
    assert build_for_seq(events, 7) == {"version": "v1", "build_id": None}


# --- build_identity: shape + env handling ---

def test_identity_has_expected_keys():
    identity = build_identity()
    assert set(identity) == {"version", "build_id", "source_sha256", "python"}


def test_identity_version_and_python_match_runtime():
    identity = build_identity()
    assert identity["version"] == courier_core.__version__
    assert identity["python"] == platform.python_version()


def test_identity_build_id_none_when_env_unset(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    assert build_identity()["build_id"] is None


def test_identity_build_id_none_when_env_empty(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "")
    assert build_identity()["build_id"] is None


def test_identity_build_id_kept_when_short(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "lane-build-42")
    assert build_identity()["build_id"] == "lane-build-42"


def test_identity_build_id_truncated_to_bound(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "x" * (MAX_BUILD_ID_LENGTH + 50))
    build_id = build_identity()["build_id"]
    assert build_id == "x" * MAX_BUILD_ID_LENGTH
    assert len(build_id) == MAX_BUILD_ID_LENGTH == 200


def test_identity_source_sha256_agrees_with_helper():
    assert build_identity()["source_sha256"] == source_sha256()


# --- source_sha256: deterministic digest ---

def test_source_sha256_is_deterministic():
    first, second = source_sha256(), source_sha256()
    assert first == second


def test_source_sha256_is_hex_or_none():
    digest = source_sha256()
    assert digest is None or (isinstance(digest, str) and _HEX64.match(digest))
