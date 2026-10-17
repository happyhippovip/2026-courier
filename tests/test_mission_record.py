from scripts.mission_record import (
    ActiveMissionRecord, ResourceClass, MissionStatus, MissionRecordValidator
)
from datetime import datetime, timezone
import time

def test_active_mission_record_validation():
    validator = MissionRecordValidator()
    now = time.monotonic()
    record = ActiveMissionRecord(
        mission_id="m100",
        attempt_id="a1",
        assigned_role_id="role-builder",
        parent_mission_id=None,
        policy_version="1.0",
        started_at=datetime.now(timezone.utc).isoformat(),
        deadline_monotonic=now + 3600,
        lease_expires_at=now + 600,
        heartbeat_at=now,
        expected_artifacts=["dist/build.exe"],
        write_scope="L6",
        resource_class=ResourceClass.HEAVY,
        finalizer_required=True,
        status=MissionStatus.RUNNING,
        last_proven_step="checkout",
        next_unproven_step="build"
    )
    validator.validate(record)

def test_pending_action_record_validation():
    from scripts.mission_record import PendingActionRecord, RiskClass, ActionStatus
    record = PendingActionRecord(
        action_id="act-001",
        priority=10,
        source_role_id="role-reviewer",
        risk_class=RiskClass.MEDIUM,
        dedupe_key="hash-key-123",
        status=ActionStatus.PENDING,
        dependency_action_ids=[],
        payload={"task": "fix schema"}
    )
    PendingActionRecord.validate(record)
