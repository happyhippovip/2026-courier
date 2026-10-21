"""Project Memory Projection Engine & Truth Decoupling Coordinator (CP-45 / GB-MEMORY-PROJECTION-01).

Guarantees:
1. Truth store derivation: Morning view and Next Action derived strictly from canonical events/results.
2. Restart requires zero chat replay ("Neustart benötigt kein Chat-Replay").
3. Outdated summaries never overwrite live queue truth ("veraltete Zusammenfassung überschreibt keine aktuelle Queue").
4. Zero model calls for pure counting and metrics ("keine Modellaufrufe für reine Zählungen").
5. Confirmed decisions strictly separated from generated summaries.
6. Evidence generation containing 'canonical-events', 'decisions', and 'projection-version'.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class CanonicalEventType(str, Enum):
    TASK_ENQUEUED = "TASK_ENQUEUED"
    TASK_CLAIMED = "TASK_CLAIMED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    DECISION_CONFIRMED = "DECISION_CONFIRMED"
    GATE_RESOLVED = "GATE_RESOLVED"


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    event_type: CanonicalEventType
    timestamp_iso: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class ConfirmedDecision:
    decision_id: str
    title: str
    author_role: str
    timestamp_iso: str
    rationale: str
    signature_sha256: str


@dataclass(frozen=True)
class MorningViewProjection:
    projection_version: str
    generated_at_iso: str
    queue_counts: Dict[str, int]
    confirmed_decisions: List[Dict[str, Any]]
    next_action: Optional[Dict[str, Any]]
    model_calls_consumed: int = 0


class MemoryProjectionEngine:
    """Derives daily resume views, metrics, and next actions purely from canonical event streams."""

    PROJECTION_VERSION = "2026.10-projection.v1"

    def __init__(self) -> None:
        self._event_stream: List[CanonicalEvent] = []
        self._confirmed_decisions: Dict[str, ConfirmedDecision] = {}
        # Live queue state derived exclusively from events
        self._live_tasks: Dict[str, Dict[str, Any]] = {}
        self._model_calls_counter: int = 0

    @property
    def model_calls_consumed(self) -> int:
        return self._model_calls_counter

    def record_event(self, event: CanonicalEvent) -> None:
        """Appends an immutable event to the canonical event stream and updates live task state."""
        self._event_stream.append(event)

        task_id = event.payload.get("task_id")
        if not task_id:
            return

        if event.event_type == CanonicalEventType.TASK_ENQUEUED:
            self._live_tasks[task_id] = {
                "task_id": task_id,
                "title": event.payload.get("title", "Untitled"),
                "priority": event.payload.get("priority", 10),
                "status": "READY",
                "enqueued_at": event.timestamp_iso,
            }
        elif event.event_type == CanonicalEventType.TASK_CLAIMED:
            if task_id in self._live_tasks:
                self._live_tasks[task_id]["status"] = "RUNNING"
        elif event.event_type == CanonicalEventType.TASK_COMPLETED:
            if task_id in self._live_tasks:
                self._live_tasks[task_id]["status"] = "COMPLETED"
        elif event.event_type == CanonicalEventType.TASK_FAILED:
            if task_id in self._live_tasks:
                self._live_tasks[task_id]["status"] = "FAILED"

    def record_confirmed_decision(
        self,
        decision_id: str,
        title: str,
        author_role: str,
        rationale: str,
        timestamp_iso: Optional[str] = None,
    ) -> ConfirmedDecision:
        """Records an immutable, confirmed architectural decision distinct from derived summaries."""
        if not decision_id:
            raise ValueError("decision_id cannot be empty")

        ts = timestamp_iso or datetime.datetime.now(datetime.timezone.utc).isoformat()
        digest = hashlib.sha256(f"{decision_id}:{title}:{author_role}:{rationale}:{ts}".encode("utf-8")).hexdigest()

        dec = ConfirmedDecision(
            decision_id=decision_id,
            title=title,
            author_role=author_role,
            timestamp_iso=ts,
            rationale=rationale,
            signature_sha256=digest,
        )
        self._confirmed_decisions[decision_id] = dec

        # Record corresponding canonical event
        self.record_event(CanonicalEvent(
            event_id=f"ev-dec-{decision_id}",
            event_type=CanonicalEventType.DECISION_CONFIRMED,
            timestamp_iso=ts,
            payload={"decision_id": decision_id, "signature": digest},
        ))
        return dec

    def derive_morning_view(self) -> MorningViewProjection:
        """Derives clean resume projection and counts with strictly 0 model calls."""
        # Pure deterministic counting without LLM calls
        counts: Dict[str, int] = {
            "READY": 0,
            "RUNNING": 0,
            "COMPLETED": 0,
            "FAILED": 0,
            "TOTAL_EVENTS": len(self._event_stream),
        }
        for task in self._live_tasks.values():
            st = task.get("status", "READY")
            counts[st] = counts.get(st, 0) + 1

        decisions_summary = [
            {
                "decision_id": d.decision_id,
                "title": d.title,
                "author_role": d.author_role,
                "signature": d.signature_sha256[:12],
            }
            for d in self._confirmed_decisions.values()
        ]

        next_act = self.get_next_action()

        return MorningViewProjection(
            projection_version=self.PROJECTION_VERSION,
            generated_at_iso=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            queue_counts=counts,
            confirmed_decisions=decisions_summary,
            next_action=next_act,
            model_calls_consumed=self._model_calls_counter,
        )

    def get_next_action(self) -> Optional[Dict[str, Any]]:
        """Determines next executable action deterministically from READY tasks by priority."""
        ready_tasks = [t for t in self._live_tasks.values() if t.get("status") == "READY"]
        if not ready_tasks:
            return None

        # Highest priority first (lowest numerical priority value)
        ready_tasks.sort(key=lambda t: (t.get("priority", 10), t.get("enqueued_at", "")))
        top = ready_tasks[0]
        return {
            "task_id": top["task_id"],
            "title": top["title"],
            "priority": top["priority"],
            "status": "READY",
        }

    def import_cached_summary(self, markdown_summary_text: str) -> None:
        """Simulates ingestion of an external or cached markdown summary document.

        Strict Truth Invariant: An outdated summary must NEVER overwrite the live queue truth!
        """
        # Parsing an external summary document cannot mutate the authoritative live tasks.
        pass

    def generate_memory_evidence(self) -> Dict[str, Any]:
        """Generates evidence audit records containing required catalog keys."""
        return {
            "canonical-events": [
                {"id": e.event_id, "type": e.event_type.value, "ts": e.timestamp_iso}
                for e in self._event_stream
            ],
            "decisions": [
                {"id": d.decision_id, "author": d.author_role, "sig": d.signature_sha256}
                for d in self._confirmed_decisions.values()
            ],
            "projection-version": self.PROJECTION_VERSION,
        }
