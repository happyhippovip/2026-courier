"""Tests for courier_core.build (Item P9 test hardening).

Covers:
- source_sha256 computation, caching, and error handling
- build_identity environment mapping and length truncation
- build_for_seq sequence scanning and boundary conditions
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

import courier_core
from courier_core.build import (
    BUILD_ID_ENV,
    MAX_BUILD_ID_LENGTH,
    build_for_seq,
    build_identity,
    source_sha256,
)
from courier_core.events import Event, EventType


# -----------------------------------------------------------------------------
# source_sha256 Tests
# -----------------------------------------------------------------------------

def test_source_sha256_computes_valid_digest():
    source_sha256.cache_clear()
    digest = source_sha256()
    assert isinstance(digest, str)
    assert len(digest) == 64
    # Deterministic caching: second call returns identical digest
    assert source_sha256() == digest


def test_source_sha256_no_files(monkeypatch):
    source_sha256.cache_clear()
    monkeypatch.setattr("pathlib.Path.glob", lambda self, pattern: [])
    digest = source_sha256()
    assert digest is None
    source_sha256.cache_clear()


def test_source_sha256_handles_oserror(monkeypatch):
    source_sha256.cache_clear()
    class BrokenPath:
        name = "broken.py"
        def read_bytes(self):
            raise OSError("permission denied")

    monkeypatch.setattr("pathlib.Path.glob", lambda self, pattern: [BrokenPath()])
    digest = source_sha256()
    assert digest is None
    source_sha256.cache_clear()


# -----------------------------------------------------------------------------
# build_identity Tests
# -----------------------------------------------------------------------------

def test_build_identity_without_env(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    ident = build_identity()
    assert ident["version"] == courier_core.__version__
    assert ident["build_id"] is None
    assert isinstance(ident["source_sha256"], (str, type(None)))
    assert isinstance(ident["python"], str)


def test_build_identity_with_valid_env(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "build-2026-v1.0.0")
    ident = build_identity()
    assert ident["build_id"] == "build-2026-v1.0.0"


def test_build_identity_truncates_long_env(monkeypatch):
    long_build_id = "x" * 300
    monkeypatch.setenv(BUILD_ID_ENV, long_build_id)
    ident = build_identity()
    assert ident["build_id"] == "x" * MAX_BUILD_ID_LENGTH
    assert len(ident["build_id"]) == 200


def test_build_identity_empty_env(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "")
    ident = build_identity()
    assert ident["build_id"] is None


# -----------------------------------------------------------------------------
# build_for_seq Tests
# -----------------------------------------------------------------------------

def _make_event(seq: int | None, event_type: EventType, payload: dict, task_id: str | None = None) -> Event:
    return Event(
        seq=seq,
        event_id=f"evt-{seq or 0}",
        schema_v=1,
        type=event_type,
        task_id=task_id if event_type is EventType.TASK_CREATED else None,
        ts_utc="2026-10-08T12:00:00Z",
        payload=payload,
        prev_hash="0" * 64,
        hash="1" * 64,
    )


def test_build_for_seq_empty_list():
    assert build_for_seq([], 10) is None


def test_build_for_seq_no_started_event():
    events = [
        _make_event(
            1,
            EventType.TASK_CREATED,
            {
                "adapter": "synthetic",
                "params": {},
                "effect_class": "idempotent",
                "max_attempts": 1,
                "lease_ttl_s": 10,
            },
            task_id="task-1",
        )
    ]
    assert build_for_seq(events, 5) is None


def test_build_for_seq_finds_nearest_preceding():
    b1 = {"version": "1.0", "build_id": "b1"}
    b2 = {"version": "1.1", "build_id": "b2"}

    events = [
        _make_event(1, EventType.CONTROLLER_STARTED, {"build": b1}),
        _make_event(2, EventType.TASK_CREATED, {
            "adapter": "synthetic", "params": {}, "effect_class": "idempotent",
            "max_attempts": 1, "lease_ttl_s": 10,
        }, task_id="task-1"),
        _make_event(5, EventType.CONTROLLER_STARTED, {"build": b2}),
        _make_event(6, EventType.TASK_CREATED, {
            "adapter": "synthetic", "params": {}, "effect_class": "idempotent",
            "max_attempts": 1, "lease_ttl_s": 10,
        }, task_id="task-2"),
    ]

    # Before any started event
    assert build_for_seq(events, 0) is None

    # Exactly at seq 1
    assert build_for_seq(events, 1) == b1

    # Between seq 1 and 5
    assert build_for_seq(events, 4) == b1

    # Exactly at seq 5
    assert build_for_seq(events, 5) == b2

    # After seq 5
    assert build_for_seq(events, 10) == b2


def test_build_for_seq_stops_when_seq_exceeded():
    b1 = {"version": "1.0", "build_id": "b1"}
    b2 = {"version": "2.0", "build_id": "b2"}

    events = [
        _make_event(1, EventType.CONTROLLER_STARTED, {"build": b1}),
        _make_event(10, EventType.CONTROLLER_STARTED, {"build": b2}),
    ]

    # Should break at seq 10 and return b1
    assert build_for_seq(events, 5) == b1
