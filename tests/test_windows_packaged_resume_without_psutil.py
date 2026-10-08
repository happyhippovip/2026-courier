"""Packaged Windows spawn must resume a suspended child without psutil.

The dist tree ships an embeddable Python with no psutil. The host still
creates the child suspended (CREATE_SUSPENDED) and imports psutil to resume
it. That import fails, the child is killed, and the claimed task never runs.
integration/v1 already resumes through the process handle. This host is Linux,
so the test stubs ntdll and does not call NtResumeProcess.
"""

import builtins
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGED_HOST = ROOT / "scripts" / "windows_worker" / "dist" / "courier_worker" / "host.py"


def _load_packaged_host():
    spec = importlib.util.spec_from_file_location(
        "packaged_windows_courier_host_resume", PACKAGED_HOST)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


H = _load_packaged_host()


class _Child:
    def __init__(self):
        self.pid = 4242
        self._handle = 7
        self.killed = False

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 1


def _block_psutil(monkeypatch):
    seen = []
    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "psutil" or name.startswith("psutil."):
            seen.append(name)
            raise ImportError("psutil is not shipped in the Windows package")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    return seen


def _windows_spawn(monkeypatch, child, resume_status):
    seen = _block_psutil(monkeypatch)
    monkeypatch.setattr(H.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        H.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200, raising=False)
    monkeypatch.setattr(H, "_job_for_child", lambda: object())
    monkeypatch.setattr(H, "_assign_to_job", lambda job, pid: None)
    monkeypatch.setattr(H, "_close_job", lambda job: None)
    monkeypatch.setattr(H.subprocess, "Popen", lambda argv, **kwargs: child)
    if hasattr(H, "_ntdll_resume"):
        monkeypatch.setattr(H, "_ntdll_resume", lambda handle: resume_status)
    return seen


def test_suspended_child_resumes_when_psutil_is_absent(tmp_path, monkeypatch):
    child = _Child()
    seen = _windows_spawn(monkeypatch, child, 0)
    run = H._spawn_contained([sys.executable, "-c", "pass"], str(tmp_path), "task-a")
    assert seen == []
    assert run.proc is child
    assert child.killed is False


def test_resume_failure_does_not_publish_a_running_child(tmp_path, monkeypatch):
    child = _Child()
    _windows_spawn(monkeypatch, child, -1)
    with pytest.raises(H.ContainmentError, match="NtResumeProcess"):
        H._spawn_contained([sys.executable, "-c", "pass"], str(tmp_path), "task-b")
    assert child.killed is True


def test_resume_without_a_process_handle_is_refused():
    child = _Child()
    child._handle = None
    with pytest.raises(H.ContainmentError, match="no process handle"):
        H._resume_process(child)
