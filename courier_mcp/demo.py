"""Bundled synthetic demo data. Not derived from any real run or person."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .state import Snapshot, parse_document


def _stamp(now: datetime, minutes: int) -> str:
    return (now - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def demo_document(now: datetime) -> dict:
    return {
        "missions": {
            "demo-mission-001": {
                "task_id": "demo-task-001",
                "status": "FINAL_DONE",
                "reason": None,
                "goal_id": "demo-goal-website",
                "updated_at": _stamp(now, 95),
                "accepted_result_id": "demo-result-001",
                "claim_event_id": "demo-claim-001",
                "evidence_ref": "demo-evidence-001",
            },
            "demo-mission-002": {
                "task_id": "demo-task-002",
                "status": "FINAL_DONE",
                "reason": None,
                "goal_id": "demo-goal-website",
                "updated_at": _stamp(now, 40),
                "accepted_result_id": "demo-result-002",
                "claim_event_id": "demo-claim-002",
                "evidence_ref": "demo-evidence-002",
            },
            "demo-mission-003": {
                "task_id": "demo-task-003",
                "status": "POSTED",
                "reason": None,
                "goal_id": "demo-goal-video",
                "updated_at": _stamp(now, 4),
                "accepted_result_id": None,
                "claim_event_id": "demo-claim-003",
                "evidence_ref": None,
            },
        }
    }


def demo_snapshot(now: datetime | None = None) -> Snapshot:
    moment = now or datetime.now(timezone.utc)
    snapshot = parse_document(demo_document(moment), source="DEMO")
    assert snapshot.readable
    return snapshot
