#!/usr/bin/env python3
"""Targeted test proving Mac Worker daemon acquire_lock mutual exclusion and stale lock recovery."""

import os
from pathlib import Path
from unittest import mock
import pytest

from scripts.mac_worker import daemon


def test_acquire_lock_success(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path)
    lock = daemon.acquire_lock("MAC-TEST-1")
    assert lock is not None
    assert lock.exists()
    assert int(lock.read_text().strip()) == os.getpid()


def test_acquire_lock_live_holder_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path)
    lock_file = tmp_path / "courier_mac_worker_MAC-TEST-2.lock"
    # Write current process pid as existing holder
    lock_file.write_text(str(os.getpid()))

    # Attempt to acquire under different mock or same alive pid
    with mock.patch("os.getpid", return_value=999999):
        # os.kill(os.getpid(), 0) will succeed because current process is alive
        lock = daemon.acquire_lock("MAC-TEST-2")
        assert lock is None


def test_acquire_lock_stale_reclaim(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path)
    lock_file = tmp_path / "courier_mac_worker_MAC-TEST-3.lock"
    # Write a pid that is dead (e.g., 99999999)
    lock_file.write_text("99999999")

    lock = daemon.acquire_lock("MAC-TEST-3")
    assert lock is not None
    assert lock.exists()
    assert int(lock.read_text().strip()) == os.getpid()
