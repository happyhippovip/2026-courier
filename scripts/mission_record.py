import dataclasses
import json
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
import jsonschema

class ResourceClass(str, Enum):
    LIGHT = "LIGHT"
    HEAVY = "HEAVY"
    CRITICAL = "CRITICAL"

class MissionStatus(str, Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    UNRESOLVED = "UNRESOLVED"

@dataclasses.dataclass
class ActiveMissionRecord:
    mission_id: str
    attempt_id: str
    assigned_role_id: str
    parent_mission_id: Optional[str]
    policy_version: str
    started_at: str
    deadline_monotonic: float
    lease_expires_at: float
    heartbeat_at: float
    expected_artifacts: List[str]
    write_scope: str
    resource_class: ResourceClass
    finalizer_required: bool
    status: MissionStatus
    last_proven_step: Optional[str] = None
    next_unproven_step: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["resource_class"] = self.resource_class.value
        d["status"] = self.status.value
        return d

class MissionRecordValidator:
    def __init__(self, schemas_dir: str = "courier_core/schemas"):
        import os
        self.schemas_dir = schemas_dir

    def validate(self, record: ActiveMissionRecord):
        import os
        path = os.path.join(self.schemas_dir, "active_mission_record.schema.json")
        with open(path, "r") as f:
            schema = json.load(f)
        jsonschema.validate(instance=record.to_dict(), schema=schema)

class RiskClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ActionStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"

@dataclasses.dataclass
class PendingActionRecord:
    action_id: str
    priority: int
    source_role_id: str
    risk_class: RiskClass
    dedupe_key: str
    status: ActionStatus
    dependency_action_ids: Optional[List[str]] = None
    payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["risk_class"] = self.risk_class.value
        d["status"] = self.status.value
        return {k: v for k, v in d.items() if v is not None}

    @staticmethod
    def validate(record: 'PendingActionRecord', schemas_dir: str = "courier_core/schemas"):
        import os
        path = os.path.join(schemas_dir, "pending_action_record.schema.json")
        with open(path, "r") as f:
            schema = json.load(f)
        jsonschema.validate(instance=record.to_dict(), schema=schema)
