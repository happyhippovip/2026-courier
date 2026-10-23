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

import hashlib
import math
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from courier_core.events import EventType
from courier_core.state_machine import RESOLVED_VERIFIED, TaskStatus
from courier_runtime.continuity import Kirby

NOT_PROVEN = "NOT_PROVEN"
COST_BLOCKED = "COST_BLOCKED"
REJECTED_FOREIGN_TASK = "REJECTED_FOREIGN_TASK"


def task_id_for(workkey: str) -> str:
    """The controller task id for a workkey: Controller.create_task derives it from the idempotency key."""
    return "task-" + hashlib.sha256(f"workkey:{workkey}".encode("utf-8")).hexdigest()[:32]


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
    """Process-exclusive lock. Not re-entrant: never nest it in one process."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt
            # LK_LOCK gives up after ten one-second tries; wait as long as flock does.
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
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


def _owns(kirby: Kirby, slot: str, workkey: str, token: int) -> bool:
    """The slot's session holds workkey with this fencing token right now."""
    session = kirby.sessions.get(slot)
    current = kirby.workkeys.get(workkey)
    return (session is not None and current is not None and session.workkey == workkey
            and current.owner == session.session_id and current.token == token)


class LedgerEngine:
    def __init__(self, controller, campaign_path: str | os.PathLike, host: str,
                 kirby_factory: Callable[[Path, str], Kirby] | None = None, spend_limit_eur: float = 0.0):
        self.controller = controller
        self.campaign_path = Path(campaign_path)
        self.lock_path = self.campaign_path.with_suffix(self.campaign_path.suffix + ".lock")
        self.host = host
        if (isinstance(spend_limit_eur, bool) or not isinstance(spend_limit_eur, (int, float))
                or not math.isfinite(spend_limit_eur) or spend_limit_eur < 0):
            raise ValueError("spend_limit_eur must be a finite number >= 0")
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
        """Claim the next workkey for slot (or resume its own). Returns (workkey, token).

        Ownership is per slot: two processes using the same slot name both resume its workkey;
        finish_turn still fences them by token and the controller by dispatch."""
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
    def submit(self, workkey: str, task_body: dict, slot: str | None = None, token: int | None = None) -> str:
        """Create the workkey's task once. Raises CostBlocked before anything is written.

        With the claiming slot and token, a blocked workkey is also parked as BLOCKED
        (reason COST_BLOCKED) so the slot moves on to the next workkey instead of stalling.
        A task that already exists (restart, replay) is returned as it is: the gate decided
        when it was created, and a changed body must not park work that is running or done."""
        existing = task_id_for(workkey)
        if self._task(existing) is not None:
            return existing
        reason = cost_admission(task_body.get("params"), self.spend_limit_eur)
        if reason is not None:
            if slot is not None and token is not None:
                with self._campaign() as kirby:
                    if _owns(kirby, slot, workkey, token):
                        kirby.on_turn_end(slot, "BLOCKED", token, reason=f"{COST_BLOCKED}: {reason}")
            raise CostBlocked(f"{workkey}: {reason}")
        body = dict(task_body, idempotency_key=f"workkey:{workkey}")
        return self.controller.create_task(body)[1]["task_id"]

    # ---- verify -> final -> next ---------------------------------------------
    def _task(self, task_id: str):
        # The controller's lock: its appends commit inside it, so no half-written row is read.
        with self.controller._locked():
            return self.controller.journal.task(task_id)

    def proof(self, task_id: str) -> str | None:
        """journal:<seq>:RESULT_ACCEPTED for a verified COMPLETE task, else None."""
        with self.controller._locked():
            task = self.controller.journal.task(task_id)
            if task is None or task.status is not TaskStatus.COMPLETE or task.resolution != RESOLVED_VERIFIED:
                return None
            for event in self.controller.journal.events(task_id=task_id):
                if (event.type is EventType.RESULT_ACCEPTED and event.result_id == task.accepted_result_id
                        and event.dispatch_id == task.dispatch_id):
                    return f"journal:{event.seq}:RESULT_ACCEPTED"
        return None

    def finish_turn(self, slot: str, workkey: str, token: int, task_id: str, checkpoint: str = "") -> str:
        """Report a provider turn. DONE only with journal proof; the result decides, not the provider."""
        if task_id != task_id_for(workkey):
            return REJECTED_FOREIGN_TASK                    # another workkey's task proves nothing here
        task = self._task(task_id)
        proof = self.proof(task_id)
        with self._campaign() as kirby:
            if not _owns(kirby, slot, workkey, token):
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
