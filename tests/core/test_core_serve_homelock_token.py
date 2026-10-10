"""P9 hardening pins for courier_core.serve file primitives (tests only).

Covers :class:`HomeLock` (exclusive per-home lock) and
:func:`load_or_create_token` (per-install API token file). No behavior
change, no network, no logging of token values.
"""

from __future__ import annotations

import os
import re
import stat

import pytest

from courier_core import serve

LOCK_NAME = "controller.lock"
TOKEN_NAME = "controller.token"
URLSAFE = re.compile(r"^[A-Za-z0-9_-]+$")


def _lock(tmp_path, name=LOCK_NAME):
    return serve.HomeLock(tmp_path / "run" / name)


# ---------------------------------------------------------------- HomeLock


def test_homelock_acquire_creates_parents_and_file(tmp_path):
    lock = _lock(tmp_path)
    assert lock.acquire() is True
    try:
        assert (tmp_path / "run" / LOCK_NAME).is_file()
    finally:
        lock.release()


def test_homelock_release_without_acquire_is_noop(tmp_path):
    _lock(tmp_path).release()


def test_homelock_double_release_is_safe(tmp_path):
    lock = _lock(tmp_path)
    assert lock.acquire() is True
    lock.release()
    lock.release()


def test_homelock_second_acquire_fails_while_held(tmp_path):
    first = _lock(tmp_path)
    assert first.acquire() is True
    try:
        assert _lock(tmp_path).acquire() is False
    finally:
        first.release()


def test_homelock_reacquire_after_release(tmp_path):
    first = _lock(tmp_path)
    assert first.acquire() is True
    first.release()
    second = _lock(tmp_path)
    assert second.acquire() is True
    second.release()


def test_homelock_same_instance_reacquire_after_release(tmp_path):
    lock = _lock(tmp_path)
    assert lock.acquire() is True
    lock.release()
    assert lock.acquire() is True
    lock.release()


def test_homelock_keeps_path(tmp_path):
    path = tmp_path / "run" / LOCK_NAME
    assert _lock(tmp_path).path == path


# ------------------------------------------------------- load_or_create_token


def test_token_created_when_missing(tmp_path):
    path = tmp_path / "run" / TOKEN_NAME
    token = serve.load_or_create_token(path)
    assert isinstance(token, str) and len(token) >= 32
    assert URLSAFE.match(token)
    assert path.is_file()


def test_token_reused_when_valid(tmp_path):
    path = tmp_path / "run" / TOKEN_NAME
    first = serve.load_or_create_token(path)
    second = serve.load_or_create_token(path)
    assert second == first


def test_token_short_value_is_replaced(tmp_path):
    path = tmp_path / "run" / TOKEN_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("too-short\n", encoding="utf-8")
    token = serve.load_or_create_token(path)
    assert len(token) >= 32


def test_token_blank_file_is_replaced(tmp_path):
    path = tmp_path / "run" / TOKEN_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("   \n", encoding="utf-8")
    token = serve.load_or_create_token(path)
    assert len(token) >= 32


def test_token_whitespace_padded_value_is_reused_stripped(tmp_path):
    path = tmp_path / "run" / TOKEN_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("  " + "x" * 40 + "\n", encoding="utf-8")
    assert serve.load_or_create_token(path) == "x" * 40


def test_token_creates_missing_parents(tmp_path):
    path = tmp_path / "deep" / "nested" / TOKEN_NAME
    token = serve.load_or_create_token(path)
    assert len(token) >= 32
    assert path.is_file()


def test_token_file_ends_with_newline(tmp_path):
    path = tmp_path / "run" / TOKEN_NAME
    serve.load_or_create_token(path)
    assert path.read_bytes().endswith(b"\n")


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only mode")
def test_token_file_is_owner_only_posix(tmp_path):
    path = tmp_path / "run" / TOKEN_NAME
    serve.load_or_create_token(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_tokens_differ_across_homes(tmp_path):
    first = serve.load_or_create_token(tmp_path / "a" / TOKEN_NAME)
    second = serve.load_or_create_token(tmp_path / "b" / TOKEN_NAME)
    assert first != second
