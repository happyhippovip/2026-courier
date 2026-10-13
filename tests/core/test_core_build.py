"""Dedicated tests for courier_core.build (P9 hardening; no behavior change)."""

from __future__ import annotations

import courier_core
from courier_core.build import (
    BUILD_ID_ENV,
    MAX_BUILD_ID_LENGTH,
    build_for_seq,
    build_identity,
    source_sha256,
)
from courier_core.events import Event, EventType


def test_source_sha256_is_stable_64_hex():
    digest = source_sha256()
    assert digest is not None
    assert len(digest) == 64
    assert digest == source_sha256()
    int(digest, 16)


def test_build_identity_fields_and_env(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    identity = build_identity()
    assert identity["version"] == courier_core.__version__
    assert identity["build_id"] is None
    assert identity["source_sha256"] == source_sha256()
    assert isinstance(identity["python"], str) and identity["python"]

    monkeypatch.setenv(BUILD_ID_ENV, "packaged-build-42")
    assert build_identity()["build_id"] == "packaged-build-42"

    monkeypatch.setenv(BUILD_ID_ENV, "x" * (MAX_BUILD_ID_LENGTH + 25))
    assert build_identity()["build_id"] == "x" * MAX_BUILD_ID_LENGTH


def test_build_for_seq_tracks_nearest_controller_started():
    started_a = Event(
        type=EventType.CONTROLLER_STARTED,
        payload={"build": {"build_id": "A"}},
    ).sealed(1, "0" * 64)
    created = Event(
        type=EventType.TASK_CREATED,
        task_id="t1",
        payload={
            "adapter": "synthetic",
            "params": {},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 5,
        },
    ).sealed(2, started_a.hash)
    started_b = Event(
        type=EventType.CONTROLLER_STARTED,
        payload={"build": {"build_id": "B"}},
    ).sealed(3, created.hash)
    complete = Event(
        type=EventType.TASK_COMPLETE,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        result_id="r1",
    ).sealed(4, started_b.hash)
    events = [started_a, created, started_b, complete]

    assert build_for_seq(events, 0) is None
    assert build_for_seq(events, 1)["build_id"] == "A"
    assert build_for_seq(events, 2)["build_id"] == "A"
    assert build_for_seq(events, 3)["build_id"] == "B"
    assert build_for_seq(events, 4)["build_id"] == "B"
