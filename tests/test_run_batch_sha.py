"""Regression: run_batch.get_git_sha must fail closed, never fabricate provenance.

Covers MUSE-C01-CONTRACT-001: the old bare ``except:`` returned
``fake-sha-<rand>`` on any git failure (indistinguishable from real
provenance in completion evidence) and even swallowed cancellation
(KeyboardInterrupt/SystemExit), breaking crash/resume accounting.
"""
import subprocess

import pytest

from scripts.run_batch import get_git_sha


def test_git_missing_returns_unknown(monkeypatch):
    def _boom(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "check_output", _boom)
    assert get_git_sha() == "UNKNOWN"


def test_git_error_returns_unknown(monkeypatch):
    def _boom(*args, **kwargs):
        raise subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])

    monkeypatch.setattr(subprocess, "check_output", _boom)
    assert get_git_sha() == "UNKNOWN"


def test_success_passthrough(monkeypatch):
    monkeypatch.setattr(
        subprocess, "check_output", lambda *args, **kwargs: b"abc123\n"
    )
    assert get_git_sha() == "abc123"


def test_cancellation_propagates(monkeypatch):
    def _cancel(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(subprocess, "check_output", _cancel)
    with pytest.raises(KeyboardInterrupt):
        get_git_sha()
