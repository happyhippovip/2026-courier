"""Targeted test: github dispatcher hygiene helpers.

- task_tmp_file must reject path-traversal task_ids from the server.
- reap_children must reap finished adapters (no zombie leak) and keep
  live ones tracked.
- python_bin must resolve the venv interpreter independent of cwd.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import courier_github_dispatcher as dispatcher


def test_task_tmp_file_accepts_normal_id():
    path = dispatcher.task_tmp_file("task-revenue-abc123")
    assert path == os.path.join(tempfile.gettempdir(), "task-revenue-abc123.json")


def test_task_tmp_file_rejects_traversal_and_junk():
    for bad in ("../../etc/evil", "/abs/path", "a/b", "", None, 123,
                "task; rm -rf", "x" * 200):
        assert dispatcher.task_tmp_file(bad) is None


def test_reap_children_reaps_finished_keeps_live(capsys):
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        remaining = dispatcher.reap_children([("t-done", done), ("t-live", live)])
        assert [t for t, _ in remaining] == ["t-live"]
        assert done.poll() is not None  # reaped, no zombie
    finally:
        live.kill()
        live.wait()


def test_reap_children_logs_adapter_failure(capsys):
    failed = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(3)"])
    failed.wait()
    assert dispatcher.reap_children([("t-fail", failed)]) == []
    assert "t-fail" in capsys.readouterr().out


def test_python_bin_prefers_repo_venv(tmp_path, monkeypatch):
    venv_python = tmp_path / "venv" / "bin" / "python3"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    monkeypatch.setattr(dispatcher, "REPO_ROOT", str(tmp_path))
    assert dispatcher.python_bin() == str(venv_python)


def test_python_bin_falls_back_without_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatcher, "REPO_ROOT", str(tmp_path))
    assert dispatcher.python_bin() == "python3"
