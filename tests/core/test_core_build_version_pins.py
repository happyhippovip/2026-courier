"""P9 test hardening for courier_core.build (version + build_id pins).

Tests only; no behavior change. Covers build_identity() env handling and
truncation, source_sha256() shape/determinism, and build_for_seq()
attribution semantics. No network, no credentials, no filesystem writes.
"""

import os
import platform
import re

import courier_core
from courier_core import build as B
from courier_core.events import Event, EventType

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _started(seq, build_payload):
    payload = {} if build_payload is None else {"build": build_payload}
    return Event(type=EventType.CONTROLLER_STARTED, payload=payload, seq=seq)


def _created(seq):
    return Event(
        type=EventType.TASK_CREATED,
        task_id="t1",
        payload={
            "adapter": "local_shell",
            "params": {},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 60,
        },
        seq=seq,
    )


def test_identity_keys_exact(monkeypatch):
    monkeypatch.delenv(B.BUILD_ID_ENV, raising=False)
    ident = B.build_identity()
    assert set(ident.keys()) == {"version", "build_id", "source_sha256", "python"}


def test_identity_version_matches_package(monkeypatch):
    monkeypatch.delenv(B.BUILD_ID_ENV, raising=False)
    assert B.build_identity()["version"] == courier_core.__version__


def test_identity_python_matches_platform(monkeypatch):
    monkeypatch.delenv(B.BUILD_ID_ENV, raising=False)
    assert B.build_identity()["python"] == platform.python_version()


def test_identity_build_id_none_when_unset(monkeypatch):
    monkeypatch.delenv(B.BUILD_ID_ENV, raising=False)
    assert B.build_identity()["build_id"] is None


def test_identity_build_id_none_when_empty(monkeypatch):
    monkeypatch.setenv(B.BUILD_ID_ENV, "")
    assert B.build_identity()["build_id"] is None


def test_identity_build_id_passthrough_short(monkeypatch):
    monkeypatch.setenv(B.BUILD_ID_ENV, "release-42")
    assert B.build_identity()["build_id"] == "release-42"


def test_identity_build_id_truncated_to_200(monkeypatch):
    monkeypatch.setenv(B.BUILD_ID_ENV, "x" * 250)
    value = B.build_identity()["build_id"]
    assert value == "x" * B.MAX_BUILD_ID_LENGTH
    assert len(value) == 200


def test_identity_build_id_exactly_200_kept(monkeypatch):
    monkeypatch.setenv(B.BUILD_ID_ENV, "y" * 200)
    assert B.build_identity()["build_id"] == "y" * 200


def test_source_sha256_shape():
    digest = B.source_sha256()
    assert digest is None or (isinstance(digest, str) and bool(HEX64.match(digest)))


def test_source_sha256_deterministic():
    assert B.source_sha256() == B.source_sha256()


def test_for_seq_empty_returns_none():
    assert B.build_for_seq([], 1) is None


def test_for_seq_no_started_returns_none():
    assert B.build_for_seq([_created(1), _created(2)], 2) is None


def test_for_seq_single_started_at_and_before_seq():
    marker = {"version": "1.0.0.dev0", "build_id": None}
    events = [_started(1, marker)]
    assert B.build_for_seq(events, 1) == marker
    assert B.build_for_seq(events, 5) == marker
    assert B.build_for_seq(events, 0) is None


def test_for_seq_later_started_wins_and_future_ignored():
    first = {"version": "a"}
    second = {"version": "b"}
    third = {"version": "c"}
    events = [_started(1, first), _started(3, second), _started(7, third)]
    assert B.build_for_seq(events, 1) == first
    assert B.build_for_seq(events, 3) == second
    assert B.build_for_seq(events, 6) == second
    assert B.build_for_seq(events, 7) == third


def test_for_seq_missing_build_key_returns_none():
    assert B.build_for_seq([_started(1, None)], 1) is None


def test_for_seq_non_started_events_ignored():
    marker = {"version": "v9"}
    events = [_created(1), _started(2, marker), _created(3)]
    assert B.build_for_seq(events, 3) == marker
    assert B.build_for_seq(events, 1) is None
