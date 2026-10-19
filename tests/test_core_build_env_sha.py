"""P9 hardening pins for courier_core.build (env + source-hash behavior).

Tests only: no behavior change. All paths are offline; no network, no
credentials, no subprocesses.
"""

from __future__ import annotations

import platform
import re

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

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _started(seq, build):
    return Event(type=EventType.CONTROLLER_STARTED, payload={"build": build}, seq=seq)


def test_identity_keys_and_version_python():
    ident = build_identity()
    assert set(ident) == {"version", "build_id", "source_sha256", "python"}
    assert ident["version"] == courier_core.__version__
    assert ident["python"] == platform.python_version()


def test_identity_no_env_means_null_build_id(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    assert build_identity()["build_id"] is None


def test_identity_empty_env_means_null_build_id(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "")
    assert build_identity()["build_id"] is None


def test_identity_short_build_id_kept(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "abc-123")
    assert build_identity()["build_id"] == "abc-123"


def test_identity_long_build_id_truncated_to_200(monkeypatch):
    assert MAX_BUILD_ID_LENGTH == 200
    monkeypatch.setenv(BUILD_ID_ENV, "x" * 500)
    build_id = build_identity()["build_id"]
    assert build_id == "x" * 200


def test_identity_boundary_200_kept_201_truncated(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "y" * 200)
    assert build_identity()["build_id"] == "y" * 200
    monkeypatch.setenv(BUILD_ID_ENV, "y" * 201)
    assert build_identity()["build_id"] == "y" * 200


def test_source_sha256_shape_and_cache():
    source_sha256.cache_clear()
    try:
        first = source_sha256()
        assert first is None or _HEX64.match(first)
        info_before = source_sha256.cache_info()
        second = source_sha256()
        info_after = source_sha256.cache_info()
        assert second == first
        assert info_after.hits == info_before.hits + 1
    finally:
        source_sha256.cache_clear()


def test_source_sha256_unreadable_sources_gives_none(monkeypatch):
    from pathlib import Path

    def _boom(self):
        raise OSError("unreadable")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    source_sha256.cache_clear()
    try:
        assert source_sha256() is None
    finally:
        source_sha256.cache_clear()


def test_build_for_seq_empty_is_none():
    assert build_for_seq([], 10) is None


def test_build_for_seq_no_started_is_none():
    events = [
        Event(type=EventType.TASK_CREATED, task_id="t", payload={
            "adapter": "s", "params": {}, "effect_class": "idempotent",
            "max_attempts": 1, "lease_ttl_s": 5}, seq=1),
    ]
    assert build_for_seq(events, 5) is None


def test_build_for_seq_picks_last_started_at_or_before_seq():
    b1 = {"version": "v1"}
    b2 = {"version": "v2"}
    events = [_started(1, b1), _started(4, b2), _started(9, {"version": "v3"})]
    assert build_for_seq(events, 4) == b2
    assert build_for_seq(events, 5) == b2
    assert build_for_seq(events, 1) == b1


def test_build_for_seq_ignores_non_started_types():
    b1 = {"version": "v1"}
    events = [
        _started(2, b1),
        Event(type=EventType.TASK_CREATED, task_id="t", payload={
            "adapter": "s", "params": {}, "effect_class": "idempotent",
            "max_attempts": 1, "lease_ttl_s": 5}, seq=3),
    ]
    assert build_for_seq(events, 3) == b1


def test_build_for_seq_seq_boundary_is_inclusive():
    b1 = {"version": "v1"}
    events = [_started(7, b1)]
    assert build_for_seq(events, 7) == b1
    assert build_for_seq(events, 6) is None


def test_build_for_seq_started_without_build_payload_is_none():
    events = [Event(type=EventType.CONTROLLER_STARTED, payload={}, seq=1)]
    assert build_for_seq(events, 1) is None


def test_identity_source_sha256_matches_direct_call(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    source_sha256.cache_clear()
    try:
        assert build_identity()["source_sha256"] == source_sha256()
    finally:
        source_sha256.cache_clear()


def test_build_id_env_name_and_cap():
    assert build_mod.BUILD_ID_ENV == "COURIER_BUILD_ID"
    assert build_mod.MAX_BUILD_ID_LENGTH == 200
