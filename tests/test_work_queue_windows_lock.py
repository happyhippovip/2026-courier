"""The work-queue lock must not write into a region another holder has locked.

Windows byte-range locks are mandatory: a write into a range that another
handle has locked fails with PermissionError. WorkQueue._lock used to write a
first byte into an empty lock file before taking the lock. Two claimants that
both saw the empty file both wrote, and the one that wrote after the other had
locked byte 0 died with PermissionError instead of waiting
(test_concurrent_claims_one_winner, windows-latest).

This test emulates the Windows semantics on any OS: a fake msvcrt with a
blocking byte lock, and a write that fails inside a region locked by another
descriptor. Both claimants are made to see the empty file, as in the race.
"""
import os
import sys
import threading
import types

from courier_core import work_queue
from courier_core.work_queue import WorkQueue


class _WindowsLocks:
    def __init__(self):
        self.cond = threading.Condition()
        self.holder = {}  # inode -> fd that holds byte 0

    def module(self):
        locks = self

        def locking(fd, mode, nbytes):
            ino = os.fstat(fd).st_ino
            with locks.cond:
                if mode == fake.LK_UNLCK:
                    locks.holder.pop(ino, None)
                    locks.cond.notify_all()
                    return
                if not locks.cond.wait_for(lambda: locks.holder.get(ino) in (None, fd), timeout=5):
                    raise OSError(36, "Resource deadlock avoided")
                locks.holder[ino] = fd

        fake = types.SimpleNamespace(LK_LOCK=1, LK_UNLCK=0, locking=locking)
        return fake


class _WindowsOs:
    """os as work_queue sees it on Windows: mandatory byte-range locks."""

    name = "nt"

    def __init__(self, locks):
        self._locks = locks

    def __getattr__(self, attr):
        return getattr(os, attr)

    def fstat(self, fd):
        real = os.fstat(fd)
        # Every claimant saw the lock file while it was still empty.
        return types.SimpleNamespace(st_size=0, st_ino=real.st_ino)

    def write(self, fd, data):
        ino = os.fstat(fd).st_ino
        with self._locks.cond:
            owner = self._locks.holder.get(ino)
        if owner is not None and owner != fd:
            raise PermissionError(13, "write into a region locked by another handle")
        return os.write(fd, data)


def test_second_claimant_waits_instead_of_writing_into_the_locked_byte(tmp_path, monkeypatch):
    locks = _WindowsLocks()
    monkeypatch.setitem(sys.modules, "msvcrt", locks.module())
    monkeypatch.setattr(work_queue, "os", _WindowsOs(locks))
    queue = WorkQueue(ledger_path=tmp_path / "ledger.jsonl")
    outcome = []

    def second():
        try:
            with queue._lock():
                outcome.append("entered")
        except Exception as exc:  # the bug: the thread dies here
            outcome.append(repr(exc))

    with queue._lock():
        thread = threading.Thread(target=second)
        thread.start()
        thread.join(timeout=0.5)
        assert outcome == [], f"second claimant did not wait for the lock: {outcome}"
    thread.join(timeout=5)
    assert outcome == ["entered"]
