import dataclasses
import json
from datetime import datetime
from enum import Enum
import jsonschema
from typing import Dict, Any, List, Optional, Union

class SourceType(str, Enum):
    CHAT_EXPORT = "CHAT_EXPORT"
    COURIER_EVENT = "COURIER_EVENT"
    WORK_RESULT = "WORK_RESULT"
    GOOGLE_ANTIGRAVITY_RESULT = "GOOGLE_ANTIGRAVITY_RESULT"

class SourceTypeWithSlack(str, Enum):
    CHAT_EXPORT = "CHAT_EXPORT"
    COURIER_EVENT = "COURIER_EVENT"
    WORK_RESULT = "WORK_RESULT"
    GOOGLE_ANTIGRAVITY_RESULT = "GOOGLE_ANTIGRAVITY_RESULT"
    SLACK = "SLACK"

class PrivacyClass(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"

@dataclasses.dataclass
class ThoughtIngestionEnvelope:
    ingestion_id: str
    source_type: SourceType
    source_message_id: str
    source_timestamp: str
    received_at: str
    content_hash: str
    content: Union[str, Dict[str, Any]]
    metadata: Dict[str, Any]
    correlation_id: str
    privacy_class: PrivacyClass

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["source_type"] = self.source_type.value
        d["privacy_class"] = self.privacy_class.value
        return d

@dataclasses.dataclass
class ThoughtMessage:
    schema_version: str
    message_id: str
    timestamp: str
    source: SourceTypeWithSlack
    payload: Dict[str, Any]
    payload_hash: str

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["source"] = self.source.value
        return d

@dataclasses.dataclass
class ThoughtCoverageLedger:
    schema_version: str
    initial_anchor: str
    earliest_available_message: Optional[Dict[str, Any]]
    latest_available_message: Optional[Dict[str, Any]]
    scanner_ranges: Dict[str, Any]
    completed_checkpoints: Dict[str, Any]
    gaps: List[Any]
    overlaps: List[Any]
    message_counts: Dict[str, Any]
    processed_messages: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

class ThoughtSchemaValidator:
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

    def validate_ingestion_envelope(self, envelope: ThoughtIngestionEnvelope):
        schema = self._load_schema("thought_ingestion_envelope.schema.json")
        jsonschema.validate(instance=envelope.to_dict(), schema=schema)

    def validate_message(self, message: ThoughtMessage):
        schema = self._load_schema("thought_message.schema.json")
        jsonschema.validate(instance=message.to_dict(), schema=schema)

    def validate_coverage_ledger(self, ledger: ThoughtCoverageLedger):
        schema = self._load_schema("thought_coverage_ledger.schema.json")
        jsonschema.validate(instance=ledger.to_dict(), schema=schema)
