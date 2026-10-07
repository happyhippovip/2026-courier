"""Test-owned Muse supervisor process lifecycle (see ops/ai/packets/WP005)."""
from __future__ import annotations

import atexit
import signal
import subprocess
import sys
import time
from typing import Optional

from runtime_state import (capture_process_identity, cleanup_group, cleanup_identity_authority,
                           identity_matches, process_group_stopped)

_MAX_CLEANUP_ROUNDS = 5
_ROUND_SLEEP_S = 0.1


class _Record:
    def __init__(self, proc, identity, label):
        self.proc = proc
        self.identity = identity
        self.label = label


class SupervisorTestReaper:
    """Registers subprocesses spawned by Muse supervisor tests; proves they exit."""

    def __init__(self):
        self._records: list[_Record] = []
        self._failures: list[str] = []

    def register(self, proc: subprocess.Popen, label: str = "") -> Optional[dict]:
        ident = capture_process_identity(proc)
        self._records.append(_Record(proc=proc, identity=ident, label=label or f"pid={proc.pid}"))
        return ident

    def register_launcher(self, launcher) -> None:
        for slot_id, proc in getattr(launcher, "children", {}).items():
            ident = getattr(launcher, "identities", {}).get(slot_id)
            if ident is None and proc is not None:
                ident = capture_process_identity(proc)
            self._records.append(_Record(proc=proc, identity=ident, label=f"slot={slot_id}"))

    def cleanup_all(self) -> None:
        errors = []
        for rec in list(self._records):
            ok, detail = self._cleanup_record(rec)
            if not ok:
                errors.append(f"{rec.label}: {detail}")
        self._records.clear()
        if errors:
            msg = "CLEANUP_NOT_PROVEN: " + "; ".join(errors)
            self._failures.append(msg)
            raise RuntimeError(msg)

    def failures(self):
        return list(self._failures)

    def _cleanup_record(self, rec: _Record):
        proc = rec.proc
        identity = rec.identity
        if proc.poll() is not None:
            if identity is None or process_group_stopped(proc, identity):
                return True, "already stopped"
        for _ in range(_MAX_CLEANUP_ROUNDS):
            if identity is None:
                return False, "missing spawn identity"
            if not cleanup_identity_authority(proc.pid, identity):
                return False, "identity no longer matches (fail closed)"
            if cleanup_group(proc, identity):
                proc.wait(timeout=5)
                if process_group_stopped(proc, identity):
                    return True, "terminated"
            time.sleep(_ROUND_SLEEP_S)
        if process_group_stopped(proc, identity):
            return True, "terminated after final check"
        return False, "process group still alive after bounded cleanup"


_GLOBAL: Optional[SupervisorTestReaper] = None


def get_reaper() -> SupervisorTestReaper:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = SupervisorTestReaper()
        atexit.register(_flush_global)
    return _GLOBAL


def _flush_global():
    global _GLOBAL
    if _GLOBAL is None:
        return
    try:
        _GLOBAL.cleanup_all()
    except RuntimeError:
        pass
    _GLOBAL = None


def detect_stale_slot_with_live_process(slot_home, pid: str, identity: Optional[dict]) -> bool:
    """True when slot state says idle/stopped but the recorded process is still alive."""
    if not pid:
        return False
    try:
        pid_i = int(pid)
    except (TypeError, ValueError):
        return False
    if identity and identity_matches(pid_i, identity):
        try:
            import os
            os.kill(pid_i, 0)
            return True
        except OSError:
            return False
    return False
