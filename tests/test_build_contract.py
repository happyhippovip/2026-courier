"""Contract pins for courier_core.build (P9-build_contract, tests only).

Pins the small attribution contract documented in courier_core/build.py:
which build wrote a lifecycle (build_identity) and which build owns a
sequence number (build_for_seq). No behavior change, no network, no
credentials, no subprocess.
"""

from __future__ import annotations

import platform
import re
from pathlib import Path

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

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _started(seq: int | None, build: dict | None):
    payload = {} if build is None else {"build": build}
    return Event(type=EventType.CONTROLLER_STARTED, payload=payload, seq=seq)


def _stopped(seq: int | None):
    return Event(type=EventType.CONTROLLER_STOPPED, payload={}, seq=seq)


# -- build_identity -----------------------------------------------------------

def test_identity_keys_version_and_python():
    identity = build_identity()
    assert set(identity) == {"version", "build_id", "source_sha256", "python"}
    assert identity["version"] == courier_core.__version__
    assert identity["python"] == platform.python_version()


def test_build_id_missing_or_empty_is_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    assert build_identity()["build_id"] is None
    monkeypatch.setenv(BUILD_ID_ENV, "")
    assert build_identity()["build_id"] is None


def test_build_id_passthrough_and_truncation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(BUILD_ID_ENV, "rel-42")
    assert build_identity()["build_id"] == "rel-42"
    long_id = "b" * (MAX_BUILD_ID_LENGTH + 50)
    monkeypatch.setenv(BUILD_ID_ENV, long_id)
    truncated = build_identity()["build_id"]
    assert truncated == long_id[:MAX_BUILD_ID_LENGTH]
    assert len(truncated) == MAX_BUILD_ID_LENGTH


def test_constants():
    assert BUILD_ID_ENV == "COURIER_BUILD_ID"
    assert MAX_BUILD_ID_LENGTH == 200


# -- source_sha256 ------------------------------------------------------------

def test_source_sha256_shape_and_stable():
    first, second = source_sha256(), source_sha256()
    assert first == second
    assert first is None or (isinstance(first, str) and SHA256_RE.match(first))


def test_source_sha256_does_not_follow_a_symlink(tmp_path):
    """A symlink inside courier_core is not source. Its bytes must not change the digest."""
    outside = tmp_path / "foreign.py"
    outside.write_bytes(b"SECRET = 'adopted'\n")
    package = Path(courier_core.__file__).resolve().parent
    link = package / "zz_symlink_probe.py"
    source_sha256.cache_clear()
    before = source_sha256()
    source_sha256.cache_clear()
    link.symlink_to(outside)
    try:
        during = source_sha256()
        assert during == before, (before, during)
    finally:
        if link.is_symlink() or link.exists():
            link.unlink()
        source_sha256.cache_clear()
    assert outside.read_bytes() == b"SECRET = 'adopted'\n"


# -- build_for_seq ------------------------------------------------------------

def test_for_seq_empty_or_no_started_is_none():
    assert build_for_seq([], 10) is None
    assert build_for_seq([_stopped(1), _stopped(5)], 10) is None


def test_for_seq_single_started_boundary():
    build = {"version": "v1"}
    assert build_for_seq([_started(4, build)], 3) is None
    assert build_for_seq([_started(4, build)], 4) == build
    assert build_for_seq([_started(4, build)], 99) == build


def test_for_seq_last_started_wins_and_future_ignored():
    first = {"version": "first"}
    second = {"version": "second"}
    events = [_started(2, first), _stopped(3), _started(7, second), _started(20, {"version": "future"})]
    assert build_for_seq(events, 1) is None
    assert build_for_seq(events, 2) == first
    assert build_for_seq(events, 6) == first
    assert build_for_seq(events, 7) == second
    assert build_for_seq(events, 19) == second
    assert build_for_seq(events, 20) == {"version": "future"}


def test_for_seq_started_without_build_payload_is_none():
    assert build_for_seq([_started(1, None)], 5) is None


def test_for_seq_non_started_events_never_attribute():
    build = {"version": "v1"}
    events = [_stopped(1), _started(2, build), _stopped(3)]
    assert build_for_seq(events, 3) == build
    assert build_for_seq([_stopped(9)], 9) is None
