"""P9 extra hardening for courier_core.build (tests-only, no behavior change).

Covers courier_core/build.py gaps beyond the open P9 build pins:
- build_identity env edge cases (whitespace, exact MAX, unicode)
- source_sha256 caching and OSError fail-closed
- build_for_seq with unsealed (seq None), missing build key, generators,
  and early-break semantics.
No network, no processes, no filesystem writes outside tmp.
"""

from __future__ import annotations

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


def _started(payload_build, seq=None):
    kwargs = {"type": EventType.CONTROLLER_STARTED, "payload": {"build": payload_build}}
    if seq is not None:
        kwargs["seq"] = seq
    return Event(**kwargs)


def test_identity_has_exact_keys():
    build_mod.source_sha256.cache_clear()
    try:
        identity = build_identity()
    finally:
        build_mod.source_sha256.cache_clear()
    assert set(identity) == {"version", "build_id", "source_sha256", "python"}
    assert identity["version"] == courier_core.__version__


def test_identity_whitespace_build_id_is_kept(monkeypatch):
    # ``or None`` treats "" as missing but whitespace is truthy and kept.
    monkeypatch.setenv(BUILD_ID_ENV, "   ")
    build_mod.source_sha256.cache_clear()
    try:
        assert build_identity()["build_id"] == "   "
    finally:
        build_mod.source_sha256.cache_clear()


def test_identity_exact_max_length_passes_through(monkeypatch):
    exact = "y" * MAX_BUILD_ID_LENGTH
    assert MAX_BUILD_ID_LENGTH == 200
    monkeypatch.setenv(BUILD_ID_ENV, exact)
    build_mod.source_sha256.cache_clear()
    try:
        assert build_identity()["build_id"] == exact
    finally:
        build_mod.source_sha256.cache_clear()


def test_identity_one_over_max_is_truncated(monkeypatch):
    long_id = "z" * (MAX_BUILD_ID_LENGTH + 1)
    monkeypatch.setenv(BUILD_ID_ENV, long_id)
    build_mod.source_sha256.cache_clear()
    try:
        got = build_identity()["build_id"]
    finally:
        build_mod.source_sha256.cache_clear()
    assert got == "z" * MAX_BUILD_ID_LENGTH
    assert len(got) == MAX_BUILD_ID_LENGTH


def test_identity_unicode_build_id_preserved(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "build-\u00e9-\u6d4b\u8bd5")
    build_mod.source_sha256.cache_clear()
    try:
        assert build_identity()["build_id"] == "build-\u00e9-\u6d4b\u8bd5"
    finally:
        build_mod.source_sha256.cache_clear()


def test_source_sha256_cached_object_reused():
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


def test_source_sha256_oserror_is_none(monkeypatch):
    import pathlib

    def boom(self):
        raise OSError("unreadable")

    monkeypatch.setattr(pathlib.Path, "read_bytes", boom)
    build_mod.source_sha256.cache_clear()
    try:
        assert source_sha256() is None
    finally:
        build_mod.source_sha256.cache_clear()


def test_build_for_seq_unsealed_started_counts():
    # seq None never triggers the early break, so it still attributes.
    events = [_started({"build_id": "U"})]
    assert build_for_seq(events, 999) == {"build_id": "U"}


def test_build_for_seq_missing_build_key_is_none():
    events = [Event(type=EventType.CONTROLLER_STARTED, payload={}, seq=1)]
    assert build_for_seq(events, 1) is None


def test_build_for_seq_accepts_generator():
    b1 = {"build_id": "G1"}
    b2 = {"build_id": "G2"}
    events = (_started(b, seq) for b, seq in [(b1, 1), (b2, 5)])
    assert build_for_seq(events, 5) == b2


def test_build_for_seq_breaks_on_first_future_seq():
    b1 = {"build_id": "early"}
    b2 = {"build_id": "late"}
    # Second event has seq 100 > target 10, so iteration stops and b2 is unseen.
    events = [_started(b1, 2), _started(b2, 100)]
    assert build_for_seq(events, 10) == b1


def test_build_for_seq_none_seq_after_break_still_unseen():
    # Once seq 50 > target 10 breaks, a later unsealed event is never reached.
    b1 = {"build_id": "first"}
    b2 = {"build_id": "shadow"}
    events = [_started(b1, 2), _started(b2, 50), _started(b2)]
    assert build_for_seq(events, 10) == b1
