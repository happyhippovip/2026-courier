"""Commit- and ACK-Boundary Architecture for Courier Durable Queue (CP-07 / P07).

Defines the exact transactional boundary at which a client/UI is permitted to confirm
to the human user that a goal or task is durably committed to disk.

Invariants (CP-07 Acceptance):
1. Confirmed (ACKed) tasks survive process termination and cold restarts.
2. Unconfirmed inputs remain preserved as drafts in the caller/client draft cache.
3. Zero secondary queues: The central store (central_state.json / courier.db) remains
   the sole authoritative queue for executable work.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class AckBoundaryError(RuntimeError):
    """Raised when an operation violates the commit/ACK boundary."""


class UncommittedCrashError(AckBoundaryError):
    """Simulated or actual crash occurred before physical disk barrier."""


@dataclass(frozen=True)
class AckReceipt:
    goal_id: str
    status: str
    committed: bool
    persisted_at: float
    sha256: str


@dataclass
class InputDraft:
    draft_id: str
    goal_text: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class ClientDraftStore:
    """Client/UI local draft cache for unconfirmed inputs (in-memory or file-backed).

    Drafts have zero executable authority and do not constitute an authoritative queue.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path
        self._drafts: dict[str, InputDraft] = {}
        if self._storage_path and self._storage_path.is_file():
            self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            for k, v in data.items():
                self._drafts[k] = InputDraft(**v)
        except (OSError, json.JSONDecodeError):
            self._drafts = {}

    def _persist(self) -> None:
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: dataclasses.asdict(v) for k, v in self._drafts.items()}
            tmp = self._storage_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self._storage_path)

    def save_draft(self, draft_id: str, goal_text: str, **metadata: Any) -> InputDraft:
        now = time.time()
        draft = self._drafts.get(draft_id)
        if draft:
            draft.goal_text = goal_text
            draft.updated_at = now
            draft.metadata.update(metadata)
        else:
            draft = InputDraft(draft_id=draft_id, goal_text=goal_text, created_at=now, updated_at=now, metadata=metadata)
            self._drafts[draft_id] = draft
        self._persist()
        return draft

    def get_draft(self, draft_id: str) -> Optional[InputDraft]:
        return self._drafts.get(draft_id)

    def clear_draft(self, draft_id: str) -> bool:
        if draft_id in self._drafts:
            del self._drafts[draft_id]
            self._persist()
            return True
        return False

    def list_drafts(self) -> list[InputDraft]:
        return list(self._drafts.values())


class DurableQueueTransactionBoundary:
    """Orchestrates the commit- and ACK-boundary between client drafts and authoritative storage."""

    @staticmethod
    def commit_and_ack(
        server_client: Any,
        draft_store: ClientDraftStore,
        draft_id: str,
        payload: dict,
        *,
        headers: Optional[dict] = None,
        simulate_crash_before_fsync: bool = False,
        simulate_crash_after_fsync_before_ack: bool = False,
    ) -> AckReceipt:
        """Submit a draft to the central authoritative store.

        Only clears the draft and returns committed ACK if the server physical
        storage barrier is confirmed.
        """
        draft = draft_store.get_draft(draft_id)
        if not draft:
            raise AckBoundaryError(f"Draft '{draft_id}' not found in draft store.")

        # Ensure idempotency key binds draft to server intake
        body = dict(payload)
        idempotency_key = body.get("idempotency_key") or f"draft-ack-{draft_id}"
        body["idempotency_key"] = idempotency_key

        if simulate_crash_before_fsync:
            # Client or network process died before physical write barrier
            # Invariant: Draft remains preserved in draft store; no ACK returned
            raise UncommittedCrashError("Simulated power loss before storage commit.")

        resp = server_client.post("/goals", headers=headers, json=body)
        status_code = getattr(resp, "status_code", None)
        data = getattr(resp, "get_json", lambda: None)() or getattr(resp, "json", lambda: None)() or {}

        if status_code not in (200, 201):
            # Server rejected or failed; draft MUST remain intact in draft store
            raise AckBoundaryError(f"Server refused commit: HTTP {status_code} {data}")

        goal_id = data.get("goal_id", "")
        if not goal_id:
            raise AckBoundaryError("Server acknowledged without a valid goal_id.")

        if simulate_crash_after_fsync_before_ack:
            # Server physically committed to disk, but connection dropped before client saw ACK.
            # Invariant: The goal is permanently stored on disk.
            # On restart, re-submitting returns the idempotent ACK.
            raise UncommittedCrashError("Connection dropped after server commit barrier.")

        # Physical commit + response verified: Now safe for UI to clear draft and display ACK
        draft_store.clear_draft(draft_id)

        canonical = json.dumps(body, sort_keys=True)
        sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return AckReceipt(
            goal_id=goal_id,
            status=data.get("status", "ACTIVE"),
            committed=True,
            persisted_at=time.time(),
            sha256=sha256,
        )

    @staticmethod
    def verify_no_second_queue(state: dict, draft_store: ClientDraftStore) -> None:
        """Assert architectural invariant: Zero secondary queues exist."""
        # Drafts must NOT have task_id or execution leases
        for d in draft_store.list_drafts():
            if "task_id" in d.metadata or "worker_id" in d.metadata or "status" in d.metadata:
                raise AckBoundaryError(f"Draft {d.draft_id} contains authoritative task fields!")

        # All authoritative tasks live in central state["tasks"]
        tasks = state.get("tasks", {})
        if not isinstance(tasks, dict):
            raise AckBoundaryError("Central state tasks is corrupted or missing.")
