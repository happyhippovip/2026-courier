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
import json
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


def _refuse_symlink(path: Path) -> None:
    if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
        raise OSError(f"{path}: refusing to follow a symlink")


def _has_receipt(path: Path, workkey: str, proof: str) -> bool:
    _refuse_symlink(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return False
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue    # a torn last line from a crash is not a receipt
        if record.get("workkey") == workkey and proof in str(record.get("checkpoint", "")):
            return True
    return False


def _skip_receipts(log: Callable) -> Callable:
    def logged(name, record):
        if name != "receipts.jsonl":
            log(name, record)
    return logged


class SingleWriterError(Exception):
    """A second writer attempted to mutate the campaign without the active writer token."""


class TaskConflict(Exception):
    """The workkey already has a task created from a different body; a human decides."""


def cost_admission(params: Any, spend_limit_eur: float = 0.0) -> str | None:
    """Return None if the task may be created, else the reason it is blocked."""
    if not isinstance(params, dict):
        return "UNKNOWN_COST: params missing"
    marker = params.get("cost_class")
    if params.get("unknown_cost") is True or (isinstance(marker, str) and marker.strip().lower() == "unknown"):
        return "UNKNOWN_COST: marked unknown"
    cost = params.get("estimated_cost_eur")
    try:
        finite = not isinstance(cost, bool) and isinstance(cost, (int, float)) and math.isfinite(cost)
    except OverflowError:
        finite = False
    if not finite:
        return "UNKNOWN_COST: no finite estimated_cost_eur"
    if cost < 0:
        return "INVALID_COST: negative estimate"
    if cost > spend_limit_eur:
        return f"OVER_LIMIT: {cost} EUR > {spend_limit_eur} EUR"
    return None


@contextmanager
def _exclusive(lock_path: Path):
    """Process-exclusive lock. Not re-entrant: never nest it in one process."""
    _refuse_symlink(lock_path)
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
                 kirby_factory: Callable[[Path, str], Kirby] | None = None, spend_limit_eur: float = 0.0,
                 writer_id: str | None = None):
        self.controller = controller
        self.campaign_path = Path(campaign_path)
        self.lock_path = self.campaign_path.with_suffix(self.campaign_path.suffix + ".lock")
        self.writer_path = Path(str(self.campaign_path) + ".writer")
        self.host = host
        self.writer_id = host if writer_id is None else writer_id
        try:
            finite_limit = (not isinstance(spend_limit_eur, bool)
                            and isinstance(spend_limit_eur, (int, float))
                            and math.isfinite(spend_limit_eur))
        except OverflowError:
            finite_limit = False
        if not finite_limit or spend_limit_eur < 0:
            raise ValueError("spend_limit_eur must be a finite number >= 0")
        self.spend_limit_eur = spend_limit_eur
        self._kirby_factory = kirby_factory or (lambda path, h: Kirby(path, h))

    def _require_writer(self) -> None:
        """Claim or keep the campaign writer token. A different writer_id is rejected."""
        path = self.writer_path
        _refuse_symlink(path)
        if path.is_file():
            owner = path.read_text(encoding="utf-8").splitlines()
            current = owner[0].strip() if owner else ""
            if current != self.writer_id:
                raise SingleWriterError("SECOND_WRITER_REJECTED")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, (self.writer_id + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    @contextmanager
    def _campaign(self):
        """Exclusive, fresh view of the campaign file; Kirby saves inside the lock."""
        _refuse_symlink(self.campaign_path)
        if self.lock_path.is_symlink() or self.writer_path.is_symlink():
            raise OSError(f"{self.campaign_path}: refusing to follow a symlink")
        with _exclusive(self.lock_path):
            self._require_writer()
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
        A task that already exists (restart, replay) is returned when the body is the same: the
        gate decided when it was created. A changed body raises TaskConflict and parks nothing,
        because the work may be running or done. ``depends_on`` is refused: the engine orders
        work by workkey, and a controller dependency would leave the slot unproven forever."""
        if "depends_on" in task_body:
            raise ValueError("the ledger engine does not take depends_on; order work by workkey")
        existing = task_id_for(workkey)
        if self._task(existing) is not None:
            from courier_core.controller import ApiError
            try:   # the controller answers an identical body with the same task and 409 otherwise
                self.controller.create_task(dict(task_body, idempotency_key=f"workkey:{workkey}"))
            except ApiError as exc:
                raise TaskConflict(f"{workkey}: {exc}") from None
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

    def _artifact_sha256(self, task_id: str, result_id: str) -> str | None:
        """Caller holds the controller lock. Digest of the accepted RESULT_READY artifacts."""
        digests = []
        for event in self.controller.journal.events(task_id=task_id):
            if event.type is not EventType.RESULT_READY or event.result_id != result_id:
                continue
            for art in (event.payload or {}).get("artifacts") or []:
                digest = art.get("sha256") if isinstance(art, dict) else None
                if isinstance(digest, str) and digest:
                    digests.append(digest)
        if not digests:
            return None
        if len(digests) == 1:
            return digests[0]
        return hashlib.sha256(",".join(digests).encode("utf-8")).hexdigest()

    def proof(self, task_id: str) -> str | None:
        """journal:<seq>:RESULT_ACCEPTED or that plus |sha256:<hex> for a verified task."""
        with self.controller._locked():
            task = self.controller.journal.task(task_id)
            if task is None or task.status is not TaskStatus.COMPLETE or task.resolution != RESOLVED_VERIFIED:
                return None
            accepted_seq = None
            for event in self.controller.journal.events(task_id=task_id):
                if (event.type is EventType.RESULT_ACCEPTED and event.result_id == task.accepted_result_id
                        and event.dispatch_id == task.dispatch_id):
                    accepted_seq = event.seq
                    break
            if accepted_seq is None:
                return None
            digest = self._artifact_sha256(task_id, task.accepted_result_id)
            params = task.params if isinstance(getattr(task, "params", None), dict) else {}
            upstreams = params.get("inputs_from")
            if isinstance(upstreams, list) and upstreams:
                for upstream in upstreams:
                    upstream_id = task_id_for(str(upstream))
                    upstream_task = self.controller.journal.task(upstream_id)
                    if (upstream_task is None or upstream_task.status is not TaskStatus.COMPLETE
                            or upstream_task.resolution != RESOLVED_VERIFIED):
                        return None
                    upstream_digest = self._artifact_sha256(upstream_id, upstream_task.accepted_result_id)
                    if upstream_digest is None or digest is None or upstream_digest != digest:
                        return None
            base = f"journal:{accepted_seq}:RESULT_ACCEPTED"
            if digest is None:
                return base
            return f"{base}|sha256:{digest}"

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
                if _has_receipt(self.campaign_path.parent / "receipts.jsonl", workkey, proof):
                    # A crash after the receipt line and before the campaign save: finish the
                    # state change, but do not write the same DONE receipt twice.
                    kirby._log = _skip_receipts(kirby._log)
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
