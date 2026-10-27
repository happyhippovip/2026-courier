"""Windows LockFile is per process. A second thread must wait, not drop the update."""
import os
import sys
import threading
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import intake_dispatcher


def test_windows_lock_serializes_threads_in_one_process(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    held = {"count": 0}
    guard = threading.Lock()

    def locking(fd, mode, nbytes):
        if mode == 1:  # LK_UNLCK
            with guard:
                held["count"] -= 1
            return
        with guard:
            if held["count"]:
                err = OSError(36, "Resource deadlock avoided")
                raise err
            held["count"] = 1

    monkeypatch.setitem(sys.modules, "msvcrt", types.SimpleNamespace(
        LK_LOCK=0, LK_UNLCK=1, locking=locking,
    ))

    state_file = str(tmp_path / "central_state.json")
    entered = []
    errors = []

    def worker(index):
        try:
            with intake_dispatcher._central_state_locked(state_file):
                entered.append(index)
        except OSError as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert sorted(entered) == list(range(8))
    assert held["count"] == 0
