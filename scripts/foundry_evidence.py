import dataclasses
import json
from datetime import datetime
from enum import Enum
import jsonschema
from typing import Dict, Any

class FounderApprovalState(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"
    PENDING = "PENDING"

class EvidenceType(str, Enum):
    ECONOMIC = "ECONOMIC"
    TECHNICAL = "TECHNICAL"
    USER_VALIDATION = "USER_VALIDATION"
    PROVIDER_COST = "PROVIDER_COST"

@dataclasses.dataclass
class DossierGoalMissionLink:
    dossier_id: str
    goal_id: str
    mission_id: str
    link_rationale: str
    timestamp_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

@dataclasses.dataclass
class VerifiedFounderReviewGate:
    gate_id: str
    review_target: str
    founder_approval: FounderApprovalState
    feedback_notes: str
    timestamp_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

@dataclasses.dataclass
class PilotEvidenceRecord:
    pilot_id: str
    evidence_type: EvidenceType
    metric: str
    result: str
    timestamp_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

class FoundrySchemaValidator:
    def __init__(self, schemas_dir: str = "courier_core/schemas"):
        import os
        self.schemas_dir = schemas_dir
        self.schemas = {}

    def _load_schema(self, schema_name: str) -> dict:
        import os
        if schema_name not in self.schemas:
            path = os.path.join(self.schemas_dir, schema_name)
            with open(path, "r") as f:
                self.schemas[schema_name] = json.load(f)
        return self.schemas[schema_name]

    def validate_link(self, link: DossierGoalMissionLink):
        schema = self._load_schema("dossier_goal_mission_link.schema.json")
        jsonschema.validate(instance=link.to_dict(), schema=schema)

    def validate_review_gate(self, gate: VerifiedFounderReviewGate):
        schema = self._load_schema("verified_founder_review_gate.schema.json")
        data = gate.to_dict()
        data["founder_approval"] = data["founder_approval"].value if isinstance(data["founder_approval"], Enum) else data["founder_approval"]
        jsonschema.validate(instance=data, schema=schema)

    def validate_evidence(self, evidence: PilotEvidenceRecord):
        schema = self._load_schema("pilot_evidence_record.schema.json")
        data = evidence.to_dict()
        data["evidence_type"] = data["evidence_type"].value if isinstance(data["evidence_type"], Enum) else data["evidence_type"]
        jsonschema.validate(instance=data, schema=schema)
