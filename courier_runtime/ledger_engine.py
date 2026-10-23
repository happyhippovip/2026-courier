"""Ledger engine: one workkey loop on top of the journal controller.

QUEUE -> CLAIM -> COST GATE -> RUN -> VERIFY -> COMPLETE -> FINAL -> NEXT

The controller (courier_core.controller) already owns claim, lease fencing,
verification and restart for a task. Kirby (courier_runtime.continuity) owns
which workkey a session works on next. Neither checks the other, so a workkey
could be marked DONE on a provider's word and a task with unknown cost could
be queued. This module joins them with three rules:

- COST GATE before the task exists: a workkey whose task has no explicit,
  finite estimate within the spend limit is never created. Unknown cost blocks.
- FINAL only with proof: a workkey becomes DONE only when its task is COMPLETE
  with resolution "verified" and the journal holds the RESULT_ACCEPTED of the
  accepted result. The proof id is written into the checkpoint and receipt.
  A provider saying "done" without that is NOT_PROVEN and the workkey stays
  claimed.
- One writer for the campaign file: every Kirby read-modify-write runs under
  an exclusive file lock and reloads from disk inside it, so two processes
  cannot claim the same workkey.

The task id is derived from the workkey (controller idempotency_key), so a
restart finds the same task and never creates or runs it twice.
"""
from __future__ import annotations

import math
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from courier_core.events import EventType
from courier_core.state_machine import RESOLVED_VERIFIED, TaskStatus
from courier_runtime.continuity import Kirby

NOT_PROVEN = "NOT_PROVEN"
COST_BLOCKED = "COST_BLOCKED"


class CostBlocked(Exception):
    """The workkey's task may not be created: its cost is unknown or over the limit."""


def cost_admission(params: Any, spend_limit_eur: float = 0.0) -> str | None:
    """Return None if the task may be created, else the reason it is blocked."""
    if not isinstance(params, dict):
        return "UNKNOWN_COST: params missing"
    if params.get("unknown_cost") is True or params.get("cost_class") == "unknown":
        return "UNKNOWN_COST: marked unknown"
    cost = params.get("estimated_cost_eur")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost):
        return "UNKNOWN_COST: no finite estimated_cost_eur"
    if cost < 0:
        return "INVALID_COST: negative estimate"
    if cost > spend_limit_eur:
        return f"OVER_LIMIT: {cost} EUR > {spend_limit_eur} EUR"
    return None


@contextmanager
def _exclusive(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class LedgerEngine:
    def __init__(self, controller, campaign_path: str | os.PathLike, host: str,
                 kirby_factory: Callable[[Path, str], Kirby] | None = None, spend_limit_eur: float = 0.0):
        self.controller = controller
        self.campaign_path = Path(campaign_path)
        self.lock_path = self.campaign_path.with_suffix(self.campaign_path.suffix + ".lock")
        self.host = host
        self.spend_limit_eur = spend_limit_eur
        self._kirby_factory = kirby_factory or (lambda path, h: Kirby(path, h))

    @contextmanager
    def _campaign(self):
        """Exclusive, fresh view of the campaign file; Kirby saves inside the lock."""
        with _exclusive(self.lock_path):
            yield self._kirby_factory(self.campaign_path, self.host)

    # ---- queue ---------------------------------------------------------------
    def add_workkeys(self, keys, priority: int = 100) -> None:
        with self._campaign() as kirby:
            kirby.add_workkeys(keys, priority)

    def open_slot(self, slot: str, provider: str) -> None:
        with self._campaign() as kirby:
            kirby.open_slot(slot, provider)

    def next(self, slot: str) -> tuple[str, int] | None:
        """Claim the next workkey for slot (or resume its own). Returns (workkey, token)."""
        with self._campaign() as kirby:
            kirby.wake(slot)
            workkey = kirby.deliver(slot)
            if workkey is None:
                session = kirby.sessions[slot]
                if session.state == "WORKING" and session.workkey:
                    return session.workkey, session.token
                return None
            return workkey, kirby.sessions[slot].token

    # ---- cost gate + task -----------------------------------------------------
    def submit(self, workkey: str, task_body: dict) -> str:
        """Create the workkey's task once. Raises CostBlocked before anything is written."""
        reason = cost_admission(task_body.get("params"), self.spend_limit_eur)
        if reason is not None:
            raise CostBlocked(f"{workkey}: {reason}")
        body = dict(task_body, idempotency_key=f"workkey:{workkey}")
        return self.controller.create_task(body)[1]["task_id"]

    # ---- verify -> final -> next ---------------------------------------------
    def proof(self, task_id: str) -> str | None:
        """journal:<seq>:RESULT_ACCEPTED for a verified COMPLETE task, else None."""
        task = self.controller.journal.task(task_id)
        if task is None or task.status is not TaskStatus.COMPLETE or task.resolution != RESOLVED_VERIFIED:
            return None
        for event in self.controller.journal.events():
            if (event.type is EventType.RESULT_ACCEPTED and event.task_id == task_id
                    and event.result_id == task.accepted_result_id and event.dispatch_id == task.dispatch_id):
                return f"journal:{event.seq}:RESULT_ACCEPTED"
        return None

    def finish_turn(self, slot: str, workkey: str, token: int, task_id: str, checkpoint: str = "") -> str:
        """Report a provider turn. DONE only with journal proof; the result decides, not the provider."""
        task = self.controller.journal.task(task_id)
        proof = self.proof(task_id)
        with self._campaign() as kirby:
            session = kirby.sessions.get(slot)
            current = kirby.workkeys.get(workkey)
            if (session is None or current is None or session.workkey != workkey
                    or current.owner != session.session_id or current.token != token):
                return "REJECTED_STALE_WRITER"
            if proof is not None:
                note = f"{checkpoint} | {proof}" if checkpoint else proof
                return kirby.on_turn_end(slot, "DONE", token, checkpoint=note)
            if task is not None and task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                return kirby.on_turn_end(slot, "FAILED_FINAL", token, checkpoint=checkpoint,
                                         reason=f"task {task.status.value}")
            if task is not None and task.status is TaskStatus.BLOCKED:
                return kirby.on_turn_end(slot, "BLOCKED", token, checkpoint=checkpoint,
                                         reason=task.last_reason or "task blocked")
            if checkpoint:
                kirby.heartbeat(slot, progress=False, checkpoint=checkpoint)
            return NOT_PROVEN
