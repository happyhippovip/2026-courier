import dataclasses
import json
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
import jsonschema

class HostOS(str, Enum):
    WINDOWS = "WINDOWS"
    MACOS = "MACOS"
    LINUX = "LINUX"
    UNKNOWN = "UNKNOWN"

class AuthorityLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    MUTABLE_L1 = "MUTABLE_L1"
    MUTABLE_L2 = "MUTABLE_L2"
    MUTABLE_L3 = "MUTABLE_L3"
    MUTABLE_L4 = "MUTABLE_L4"
    MUTABLE_L5 = "MUTABLE_L5"
    MUTABLE_L6 = "MUTABLE_L6"

class HandoffStatus(str, Enum):
    NEW = "NEW"
    CHANGED = "CHANGED"
    BLOCKING = "BLOCKING"
    RESOLVED = "RESOLVED"
    UNCHANGED = "UNCHANGED"
    UNKNOWN = "UNKNOWN"
    NO_MATERIAL_DELTA = "NO_MATERIAL_DELTA"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"

class ContinuationGate(str, Enum):
    OPEN = "OPEN"
    BLOCKED = "BLOCKED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    DEPENDENCY_REQUIRED = "DEPENDENCY_REQUIRED"

@dataclasses.dataclass
class EvidenceItem:
    path: str
    hash: str
    type: str
    command: Optional[str] = None
    result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        return {k: v for k, v in d.items() if v is not None}

@dataclasses.dataclass
class AgentHandoffReceipt:
    origin: str
    agent_instance: str
    assignment_id: str
    host_os: HostOS
    authority: AuthorityLevel
    created_at: str
    status: HandoffStatus
    new_findings: List[str]
    changed_findings: List[str]
    resolved_findings: List[str]
    blocking_findings: List[str]
    evidence: List[EvidenceItem]
    actions_taken: List[str]
    production_files_modified: List[str]
    waiting_for: List[str]
    safe_parallel_work: List[str]
    next_independent_task: str
    recommended_next_agent: str
    continuation_gate: ContinuationGate
    wait_resume_contract: str
    receipt_hash: str
    previous_receipt_hash: Optional[str] = None
    source_freeze_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["host_os"] = self.host_os.value
        d["authority"] = self.authority.value
        d["status"] = self.status.value
        d["continuation_gate"] = self.continuation_gate.value
        d["evidence"] = [e.to_dict() for e in self.evidence]
        return d

class HandoffValidator:
    def __init__(self, schemas_dir: str = "courier_core/schemas"):
        import os
        self.schemas_dir = schemas_dir

    def validate(self, receipt: AgentHandoffReceipt):
        import os
        path = os.path.join(self.schemas_dir, "agent_handoff_receipt.schema.json")
        with open(path, "r") as f:
            schema = json.load(f)
        jsonschema.validate(instance=receipt.to_dict(), schema=schema)
