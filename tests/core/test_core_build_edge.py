"""P9 hardening for courier_core.build (edge paths).

Tests only; no behavior change. Complements the existing
test_core_build.py / test_core_build_identity.py /
test_core_build_attribution.py coverage with fail-closed edges:
source digest unreadable or empty, cache behavior, build-id
boundary handling, and build_for_seq with missing keys, None
seq values, generator input, and seq filtering. No network,
no credentials.
"""

from __future__ import annotations

import os
import platform
from unittest.mock import MagicMock

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
    source_sha256.cache_clear()
    try:
        yield
    finally:
        source_sha256.cache_clear()


def _started(build, seq):
    return Event(type=EventType.CONTROLLER_STARTED, payload={"build": build}, seq=seq)


def _started_no_build_key(seq):
    return Event(type=EventType.CONTROLLER_STARTED, payload={}, seq=seq)


def _stopped(seq):
    return Event(type=EventType.CONTROLLER_STOPPED, payload={}, seq=seq)


def test_source_sha256_none_when_no_py_files(monkeypatch):
    fake_package = MagicMock()
    fake_package.glob.return_value = []
    fake_path = MagicMock()
    fake_path.resolve.return_value.parent = fake_package
    monkeypatch.setattr(build_mod, "Path", lambda *a, **k: fake_path)
    assert source_sha256() is None


def test_source_sha256_none_on_read_error(monkeypatch):
    bad_file = MagicMock()
    bad_file.name = "build.py"
    bad_file.read_bytes.side_effect = OSError("unreadable")
    fake_package = MagicMock()
    fake_package.glob.return_value = [bad_file]
    fake_path = MagicMock()
    fake_path.resolve.return_value.parent = fake_package
    monkeypatch.setattr(build_mod, "Path", lambda *a, **k: fake_path)
    assert source_sha256() is None


def test_source_sha256_is_cached(monkeypatch):
    assert source_sha256.cache_info().maxsize == 1
    first = source_sha256()
    info_after_first = source_sha256.cache_info()
    second = source_sha256()
    info_after_second = source_sha256.cache_info()
    assert first == second
    assert info_after_second.hits == info_after_first.hits + 1


def test_build_identity_empty_string_env_is_none(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "")
    identity = build_identity()
    assert identity["build_id"] is None
    assert identity["version"] == courier_core.__version__
    assert identity["python"] == platform.python_version()


def test_build_identity_exact_200_chars_not_truncated(monkeypatch):
    value = "x" * MAX_BUILD_ID_LENGTH
    assert MAX_BUILD_ID_LENGTH == 200
    monkeypatch.setenv(BUILD_ID_ENV, value)
    assert build_identity()["build_id"] == value


def test_build_identity_201_chars_truncated_to_200(monkeypatch):
    monkeypatch.setenv(BUILD_ID_ENV, "y" * (MAX_BUILD_ID_LENGTH + 1))
    result = build_identity()["build_id"]
    assert result == "y" * MAX_BUILD_ID_LENGTH
    assert len(result) == 200


def test_build_identity_reports_version_and_python(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    monkeypatch.setattr(build_mod, "source_sha256", lambda: "0" * 64)
    identity = build_identity()
    assert identity == {
        "version": courier_core.__version__,
        "build_id": None,
        "source_sha256": "0" * 64,
        "python": platform.python_version(),
    }


def test_build_for_seq_empty_returns_none():
    assert build_for_seq([], 10) is None
    assert build_for_seq(iter([]), 10) is None


def test_build_for_seq_no_started_returns_none():
    events = [_stopped(1), _stopped(2)]
    assert build_for_seq(events, 2) is None


def test_build_for_seq_missing_build_key_returns_none():
    events = [_started_no_build_key(1), _stopped(2)]
    assert build_for_seq(events, 2) is None


def test_build_for_seq_none_build_value_returns_none():
    events = [_started(None, 1)]
    assert build_for_seq(events, 1) is None


def test_build_for_seq_none_seq_is_processed():
    # Events without seq never trigger the early break, so a None-seq
    # CONTROLLER_STARTED counts even when the target seq is 0.
    events = [_started({"build_id": "A"}, None), _stopped(5)]
    assert build_for_seq(events, 0) == {"build_id": "A"}


def test_build_for_seq_ignores_builds_after_target():
    events = [_started({"build_id": "A"}, 1), _started({"build_id": "B"}, 3)]
    assert build_for_seq(events, 1) == {"build_id": "A"}
    assert build_for_seq(events, 2) == {"build_id": "A"}
    assert build_for_seq(events, 3) == {"build_id": "B"}


def test_build_for_seq_accepts_generator():
    def gen():
        yield _started({"build_id": "A"}, 1)
        yield _stopped(2)
        yield _started({"build_id": "B"}, 3)

    assert build_for_seq(gen(), 2) == {"build_id": "A"}
    assert build_for_seq(gen(), 3) == {"build_id": "B"}


def test_build_for_seq_last_started_wins_before_target():
    events = [
        _started({"build_id": "A"}, 1),
        _started_no_build_key(2),
        _stopped(3),
    ]
    # A missing "build" key journals None, so the last STARTED clears it.
    assert build_for_seq(events, 3) is None
    assert build_for_seq(events, 1) == {"build_id": "A"}


def test_build_id_env_absent_is_none(monkeypatch):
    monkeypatch.delenv(BUILD_ID_ENV, raising=False)
    assert os.environ.get(BUILD_ID_ENV) is None
    assert build_identity()["build_id"] is None
