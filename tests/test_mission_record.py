from pathlib import Path

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


def _mission():
    now = time.monotonic()
    return ActiveMissionRecord(
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
    )


def _action():
    from scripts.mission_record import PendingActionRecord, RiskClass, ActionStatus
    return PendingActionRecord(
        action_id="act-001",
        priority=10,
        source_role_id="role-reviewer",
        risk_class=RiskClass.MEDIUM,
        dedupe_key="hash-key-123",
        status=ActionStatus.PENDING,
    )


def test_schema_file_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside-schema.json"
    outside.write_text("true\n", encoding="utf-8")
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "active_mission_record.schema.json").symlink_to(outside)
    (schema_dir / "pending_action_record.schema.json").symlink_to(outside)

    def run(call):
        try:
            call()
            return None
        except ValueError as exc:
            return str(exc)

    file_mission = run(lambda: MissionRecordValidator(str(schema_dir)).validate(_mission()))
    file_action = run(lambda: _action().validate(_action(), str(schema_dir)))

    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "active_mission_record.schema.json").write_text("true\n", encoding="utf-8")
    (parent_outside / "pending_action_record.schema.json").write_text("true\n", encoding="utf-8")
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-schemas"
    linked.symlink_to(parent_outside)
    parent_mission = run(lambda: MissionRecordValidator(str(linked)).validate(_mission()))
    parent_action = run(lambda: _action().validate(_action(), str(linked)))
    names = sorted(path.name for path in parent_outside.iterdir())
    assert (
        file_mission,
        file_action,
        parent_mission,
        parent_action,
        outside.read_text(encoding="utf-8"),
        names,
    ) == (
        "refusing to follow a symlink",
        "refusing to follow a symlink",
        "refusing to follow a symlink",
        "refusing to follow a symlink",
        "true\n",
        ["active_mission_record.schema.json", "keep.txt", "pending_action_record.schema.json"],
    )
