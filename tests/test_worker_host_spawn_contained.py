"""P9 test hardening for courier_worker.host: spawn containment + handle edges.

Pins the offline, deterministic contracts of ``_spawn_contained`` and
``ContainedRun`` without starting any real process and without network:

- EMFILE/ENFILE at spawn becomes ``ResourcePaused`` (exactly once, no
  retry); any other spawn ``OSError`` becomes ``ContainmentError``.
- ``ContainedRun`` handle semantics: pid/group passthrough, ``wait``
  timeout mapping, ``tree_alive`` signal probing, and the
  SIGTERM-then-SIGKILL escalation of ``terminate_tree``.
"""
from __future__ import annotations

import errno
import os
import signal
import subprocess

import pytest

import courier_worker.host as H
from courier_worker.host import (
    ContainedRun,
    ContainmentError,
    ResourcePaused,
)

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="POSIX signal semantics")


class _FakeProc:
    """Stand-in for subprocess.Popen; never starts a process."""

    def __init__(self, pid=4242, poll_result=None):
        self.pid = pid
        self._poll_result = poll_result
        self._wait_script = []
        self.wait_calls = []

    def queue_wait(self, *results):
        self._wait_script.extend(results)
        return self

    def poll(self):
        return self._poll_result

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self._wait_script:
            result = self._wait_script.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return self._poll_result


class _FakePopen:
    """Records constructor kwargs; returns a scripted proc or raises."""

    instances = []

    def __init__(self, proc=None, error=None):
        self._proc = proc if proc is not None else _FakeProc()
        self._error = error
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._error is not None:
            raise self._error
        return self._proc


def _spawn(monkeypatch, tmp_path, argv=("echo-stub", "a"), error=None):
    fake = _FakePopen(error=error)
    monkeypatch.setattr(subprocess, "Popen", fake)
    run = H._spawn_contained(list(argv), str(tmp_path), "task-x")
    return fake, run


# -- _spawn_contained ----------------------------------------------------------

def test_spawn_returns_contained_handle_with_stdio_paths(monkeypatch, tmp_path):
    fake, run = _spawn(monkeypatch, tmp_path)
    assert isinstance(run, ContainedRun)
    assert run.stdout_path == os.path.join(str(tmp_path), "task-x.out")
    assert run.stderr_path == os.path.join(str(tmp_path), "task-x.err")
    assert os.path.isfile(run.stdout_path)
    assert os.path.isfile(run.stderr_path)


@POSIX_ONLY
def test_spawn_wires_containment_kwargs(monkeypatch, tmp_path):
    fake, _run = _spawn(monkeypatch, tmp_path, argv=("prog", "--flag"))
    (args, kwargs), = fake.calls
    assert list(args[0]) == ["prog", "--flag"]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["close_fds"] is True
    assert kwargs["start_new_session"] is True


@POSIX_ONLY
def test_spawn_job_is_none_on_posix(monkeypatch, tmp_path):
    _fake, run = _spawn(monkeypatch, tmp_path)
    assert run.job is None


@pytest.mark.parametrize("code", [errno.EMFILE, errno.ENFILE])
def test_spawn_fd_exhaustion_becomes_resource_paused(monkeypatch, tmp_path, code):
    error = OSError(code, os.strerror(code))
    with pytest.raises(ResourcePaused) as caught:
        _spawn(monkeypatch, tmp_path, error=error)
    assert "fd-exhaustion" in str(caught.value)


def test_spawn_other_oserror_becomes_containment_error(monkeypatch, tmp_path):
    error = OSError(errno.ENOENT, os.strerror(errno.ENOENT))
    with pytest.raises(ContainmentError, match="spawn failed"):
        _spawn(monkeypatch, tmp_path, error=error)


# -- ContainedRun handle semantics ----------------------------------------------

def test_pid_and_group_id_follow_proc_pid(tmp_path):
    run = ContainedRun(_FakeProc(pid=4242), None, "o", "e")
    assert run.pid == 4242
    if os.name == "nt":
        assert run.group_id() is None
    else:
        assert run.group_id() == 4242


def test_poll_passes_through_proc_state(tmp_path):
    assert ContainedRun(_FakeProc(poll_result=None), None, "o", "e").poll() is None
    assert ContainedRun(_FakeProc(poll_result=3), None, "o", "e").poll() == 3


def test_wait_maps_timeout_expired_to_none(tmp_path):
    proc = _FakeProc().queue_wait(subprocess.TimeoutExpired("x", 1.0))
    assert ContainedRun(proc, None, "o", "e").wait(timeout=1.0) is None


def test_wait_returns_exit_code(tmp_path):
    proc = _FakeProc().queue_wait(0)
    assert ContainedRun(proc, None, "o", "e").wait(timeout=1.0) == 0


def test_tree_alive_true_when_group_signallable(monkeypatch):
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: None)
    assert ContainedRun(_FakeProc(pid=4242), None, "o", "e").tree_alive() is True


def test_tree_alive_false_when_group_is_gone(monkeypatch):
    def _gone(pgid, sig):
        raise ProcessLookupError("gone")

    monkeypatch.setattr(os, "killpg", _gone)
    assert ContainedRun(_FakeProc(pid=4242), None, "o", "e").tree_alive() is False


def test_tree_alive_true_on_permission_error(monkeypatch):
    def _denied(pgid, sig):
        raise PermissionError("denied")

    monkeypatch.setattr(os, "killpg", _denied)
    assert ContainedRun(_FakeProc(pid=4242), None, "o", "e").tree_alive() is True


@POSIX_ONLY
def test_terminate_tree_terms_then_reaps_without_kill(monkeypatch):
    signals = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: signals.append(sig))
    proc = _FakeProc(pid=4242, poll_result=None).queue_wait(0)
    ContainedRun(proc, None, "o", "e").terminate_tree(grace=0.01)
    assert signals == [signal.SIGTERM]


@POSIX_ONLY
def test_terminate_tree_escalates_to_sigkill_on_timeout(monkeypatch):
    signals = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: signals.append(sig))
    proc = _FakeProc(pid=4242, poll_result=None).queue_wait(
        subprocess.TimeoutExpired("x", 0.01), -9
    )
    ContainedRun(proc, None, "o", "e").terminate_tree(grace=0.01)
    assert signals == [signal.SIGTERM, signal.SIGKILL]


@POSIX_ONLY
def test_terminate_tree_dead_root_skips_sigkill_when_group_gone(monkeypatch):
    signals = []

    def _killpg(pgid, sig):
        signals.append(sig)
        if sig == 0:
            raise ProcessLookupError("group empty")

    monkeypatch.setattr(os, "killpg", _killpg)
    proc = _FakeProc(pid=4242, poll_result=0)
    ContainedRun(proc, None, "o", "e").terminate_tree(grace=0.01)
    assert signals[0] == signal.SIGTERM
    assert signal.SIGKILL not in signals


@POSIX_ONLY
def test_terminate_tree_sigterm_denied_raises_containment(monkeypatch):
    def _denied(pgid, sig):
        raise PermissionError("denied")

    monkeypatch.setattr(os, "killpg", _denied)
    proc = _FakeProc(pid=4242, poll_result=None)
    with pytest.raises(ContainmentError, match="cannot signal owned group"):
        ContainedRun(proc, None, "o", "e").terminate_tree(grace=0.01)


def test_close_with_no_job_is_a_noop():
    ContainedRun(_FakeProc(), None, "o", "e")._close()
