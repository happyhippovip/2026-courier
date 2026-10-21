"""Tests for CP-45 / CQ-45 / GB-MEMORY-PROJECTION-01: Project Memory Projection Engine.

Verifies:
1. Morning view and metrics derived with zero model calls ("keine Modellaufrufe für reine Zählungen").
2. Restart and Next Action derived strictly from canonical events without chat replay ("Neustart benötigt kein Chat-Replay").
3. Outdated summaries never overwrite live queue truth ("veraltete Zusammenfassung überschreibt keine aktuelle Queue").
4. Confirmed decisions preserved immutably with cryptographic signatures, separated from summaries.
5. Evidence structure generation containing ['canonical-events', 'decisions', 'projection-version'].
"""

import pytest

from courier_core.memory_projection_engine import (
    CanonicalEvent,
    CanonicalEventType,
    MemoryProjectionEngine,
)


def test_morning_view_derived_with_zero_model_calls():
    """Deriving the morning view and counts consumes strictly 0 model calls."""
    engine = MemoryProjectionEngine()

    engine.record_event(CanonicalEvent(
        event_id="ev-1",
        event_type=CanonicalEventType.TASK_ENQUEUED,
        timestamp_iso="2026-10-21T08:00:00Z",
        payload={"task_id": "t-1", "title": "Setup database", "priority": 1},
    ))
    engine.record_event(CanonicalEvent(
        event_id="ev-2",
        event_type=CanonicalEventType.TASK_ENQUEUED,
        timestamp_iso="2026-10-21T08:05:00Z",
        payload={"task_id": "t-2", "title": "Run migrations", "priority": 2},
    ))
    engine.record_event(CanonicalEvent(
        event_id="ev-3",
        event_type=CanonicalEventType.TASK_CLAIMED,
        timestamp_iso="2026-10-21T08:10:00Z",
        payload={"task_id": "t-1"},
    ))

    morning_view = engine.derive_morning_view()

    assert morning_view.projection_version == "2026.10-projection.v1"
    assert morning_view.queue_counts["RUNNING"] == 1
    assert morning_view.queue_counts["READY"] == 1
    assert morning_view.queue_counts["TOTAL_EVENTS"] == 3
    # Absolute contract invariant: 0 model calls for counts/metrics
    assert morning_view.model_calls_consumed == 0


def test_next_action_derived_strictly_without_chat_replay():
    """Next action is computed deterministically from canonical priority queue without chat replay."""
    engine = MemoryProjectionEngine()

    engine.record_event(CanonicalEvent(
        event_id="ev-10",
        event_type=CanonicalEventType.TASK_ENQUEUED,
        timestamp_iso="2026-10-21T09:00:00Z",
        payload={"task_id": "task-low-priority", "title": "Optional UI polish", "priority": 50},
    ))
    engine.record_event(CanonicalEvent(
        event_id="ev-11",
        event_type=CanonicalEventType.TASK_ENQUEUED,
        timestamp_iso="2026-10-21T09:05:00Z",
        payload={"task_id": "task-high-priority", "title": "Critical security hotfix", "priority": 1},
    ))

    next_act = engine.get_next_action()
    assert next_act is not None
    assert next_act["task_id"] == "task-high-priority"
    assert next_act["status"] == "READY"


def test_outdated_summary_does_not_overwrite_live_queue():
    """Outdated external markdown summaries cannot overwrite the authoritative live queue."""
    engine = MemoryProjectionEngine()

    engine.record_event(CanonicalEvent(
        event_id="ev-20",
        event_type=CanonicalEventType.TASK_ENQUEUED,
        timestamp_iso="2026-10-21T10:00:00Z",
        payload={"task_id": "task-live-auth", "title": "Auth token refresh", "priority": 5},
    ))

    # Obsolete markdown summary claiming everything is idle/empty
    obsolete_markdown = (
        "# Status Report Yesterday\n"
        "All queues are empty. No active work pending.\n"
    )
    engine.import_cached_summary(obsolete_markdown)

    # Live queue remains completely intact and uncorrupted
    morning_view = engine.derive_morning_view()
    assert morning_view.queue_counts["READY"] == 1
    assert engine.get_next_action()["task_id"] == "task-live-auth"


def test_confirmed_decisions_separated_from_ephemeral_summaries():
    """Confirmed architectural decisions carry cryptographic signatures and remain decoupled from summaries."""
    engine = MemoryProjectionEngine()

    dec = engine.record_confirmed_decision(
        decision_id="DEC-ZERO-COST-01",
        title="Zero Autonomous External Spend Boundary",
        author_role="HUMAN_OWNER",
        rationale="All autonomous work must consume 0.00 EUR without payment APIs.",
        timestamp_iso="2026-10-21T07:00:00Z",
    )

    assert dec.decision_id == "DEC-ZERO-COST-01"
    assert dec.author_role == "HUMAN_OWNER"
    assert len(dec.signature_sha256) == 64

    # Verify decision is surfaced in morning view
    view = engine.derive_morning_view()
    assert len(view.confirmed_decisions) == 1
    assert view.confirmed_decisions[0]["decision_id"] == "DEC-ZERO-COST-01"


def test_evidence_generation():
    """Validates required catalog evidence keys: ['canonical-events', 'decisions', 'projection-version']."""
    engine = MemoryProjectionEngine()
    engine.record_event(CanonicalEvent(
        event_id="ev-test-1",
        event_type=CanonicalEventType.TASK_ENQUEUED,
        timestamp_iso="2026-10-21T11:00:00Z",
        payload={"task_id": "t-test"},
    ))
    engine.record_confirmed_decision(
        decision_id="DEC-TEST-01",
        title="Test Invariant",
        author_role="ARCHITECT",
        rationale="Proof",
    )

    evidence = engine.generate_memory_evidence()

    assert "canonical-events" in evidence
    assert "decisions" in evidence
    assert "projection-version" in evidence

    assert len(evidence["canonical-events"]) == 2  # 1 enqueue + 1 decision event
    assert len(evidence["decisions"]) == 1
    assert evidence["projection-version"] == "2026.10-projection.v1"
