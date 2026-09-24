import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.windows_worker import daemon


def test_structured_stale_lock_is_reclaimed(monkeypatch, tmp_path):
    worker_id = "WINDOWS-STRUCTURED-STALE"
    lock = tmp_path / f"courier_worker_{worker_id}.lock"

    lock.write_text(
        json.dumps(
            {
                "worker_id": worker_id,
                "pid": os.getpid(),
                "process_create_time": 0,
                "executable": sys.executable,
                "daemon_path": str(Path(daemon.__file__).resolve()),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(daemon.tempfile, "gettempdir", lambda: str(tmp_path))

    acquired = daemon.acquire_lock(worker_id)

    try:
        assert acquired == lock
        assert lock.read_text(encoding="utf-8").strip() == str(os.getpid())
    finally:
        lock.unlink(missing_ok=True)


def test_structured_live_lock_is_not_stolen(monkeypatch, tmp_path):
    worker_id = "WINDOWS-STRUCTURED-LIVE"
    lock = tmp_path / f"courier_worker_{worker_id}.lock"

    current = daemon.psutil.Process(os.getpid())

    lock.write_text(
        json.dumps(
            {
                "worker_id": worker_id,
                "pid": os.getpid(),
                "process_create_time": current.create_time(),
                "executable": sys.executable,
                "daemon_path": str(Path(daemon.__file__).resolve()),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(daemon.tempfile, "gettempdir", lambda: str(tmp_path))

    assert daemon.acquire_lock(worker_id) is None
    assert lock.exists()
