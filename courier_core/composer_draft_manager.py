"""Composer Draft Manager & Concurrent Typing Coordinator (CP-41 / GB-COMPOSER-DRAFT-01).

Guarantees:
1. Preservation of concurrent user input typed while submit is in-flight.
2. Surgical deletion of only the acknowledged draft snapshot on server ACK.
3. Strict idempotency protecting against double-clicks and network retries (zero duplicate goals).
4. Evidence generation containing 'draft-state', 'client-request-id', and 'ACK-handler'.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


class SnapshotStatus(str, Enum):
    PENDING_SUBMIT = "PENDING_SUBMIT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"


class DuplicateSubmitError(Exception):
    """Raised when an identical in-flight submit request is duplicated without retry clearance."""


class SnapshotNotFoundError(Exception):
    """Raised when an ACK arrives for an unknown or unrecorded client request ID."""


@dataclass
class DraftSnapshot:
    snapshot_id: str
    client_request_id: str
    content: str
    timestamp_iso: str
    status: SnapshotStatus = SnapshotStatus.PENDING_SUBMIT
    associated_goal_id: Optional[str] = None
    error_reason: Optional[str] = None


class ComposerDraftManager:
    """Manages composer buffer states, in-flight submission snapshots, and surgical draft deletion."""

    def __init__(self, initial_text: str = "") -> None:
        self._current_text: str = initial_text
        self._snapshots: Dict[str, DraftSnapshot] = {}
        self._acknowledged_requests: Set[str] = set()
        self._created_goals: List[Dict[str, Any]] = []

    @property
    def current_text(self) -> str:
        return self._current_text

    def set_current_text(self, text: str) -> None:
        """Updates the active composer text buffer as user types."""
        self._current_text = text

    def append_current_text(self, additional_text: str) -> None:
        """Appends text to the active composer buffer (simulating parallel typing)."""
        self._current_text += additional_text

    def create_submit_snapshot(self, client_request_id: str) -> DraftSnapshot:
        """Captures a frozen draft snapshot of current text for submission.

        Protects against double-click and rapid retries by reusing in-flight or ACKed requests.
        """
        if not client_request_id:
            raise ValueError("client_request_id cannot be empty")

        # Double-click / replay check
        if client_request_id in self._snapshots:
            existing = self._snapshots[client_request_id]
            if existing.status == SnapshotStatus.PENDING_SUBMIT:
                # Double-click detected: return existing snapshot without duplicating submission
                return existing
            if existing.status == SnapshotStatus.ACKNOWLEDGED:
                # Already processed
                return existing

        snapshot = DraftSnapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:12]}",
            client_request_id=client_request_id,
            content=self._current_text,
            timestamp_iso=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            status=SnapshotStatus.PENDING_SUBMIT,
        )
        self._snapshots[client_request_id] = snapshot
        return snapshot

    def handle_ack(self, client_request_id: str, goal_id: str) -> bool:
        """Handles server ACK confirming goal creation.

        Surgically removes only the confirmed draft snapshot while preserving
        any concurrent user input typed while submit was in flight.
        Guarantees idempotency: duplicate ACKs create no duplicate goals.
        """
        if client_request_id not in self._snapshots:
            raise SnapshotNotFoundError(f"No snapshot found for request ID: {client_request_id}")

        snapshot = self._snapshots[client_request_id]

        # Idempotency guard: if already acknowledged, do not create duplicate goal
        if client_request_id in self._acknowledged_requests:
            return False  # Already handled, idempotent no-op

        snapshot.status = SnapshotStatus.ACKNOWLEDGED
        snapshot.associated_goal_id = goal_id
        self._acknowledged_requests.add(client_request_id)

        self._created_goals.append({
            "goal_id": goal_id,
            "client_request_id": client_request_id,
            "content": snapshot.content,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

        # Surgical Draft Deletion:
        # If user text exactly matches submitted snapshot, clear buffer.
        if self._current_text == snapshot.content:
            self._current_text = ""
        # If user typed additional text concurrently while submit was in flight
        # (e.g. current text starts with submitted content), preserve the new suffix.
        elif self._current_text.startswith(snapshot.content):
            self._current_text = self._current_text[len(snapshot.content):].lstrip("\r\n ")
        # If user completely edited or wrote something new, preserve current text as is.
        else:
            pass

        return True

    def handle_failure(self, client_request_id: str, reason: str) -> None:
        """Handles submission failure, marking snapshot failed but preserving user input."""
        if client_request_id in self._snapshots:
            snap = self._snapshots[client_request_id]
            snap.status = SnapshotStatus.FAILED
            snap.error_reason = reason

    def list_created_goals(self) -> List[Dict[str, Any]]:
        return list(self._created_goals)

    def generate_composer_evidence(self) -> Dict[str, Any]:
        """Generates evidence audit records containing required catalog keys."""
        return {
            "draft-state": {
                "current_buffer_length": len(self._current_text),
                "in_flight_count": sum(1 for s in self._snapshots.values() if s.status == SnapshotStatus.PENDING_SUBMIT),
                "acknowledged_count": len(self._acknowledged_requests),
            },
            "client-request-id": list(self._snapshots.keys()),
            "ACK-handler": {
                "created_goals_count": len(self._created_goals),
                "goals": [g["goal_id"] for g in self._created_goals],
            },
        }
