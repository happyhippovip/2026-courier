import json
import jsonschema
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List

@dataclass
class SessionHandoff:
    project_identity: str
    current_gate: str
    current_sha: str
    completed_work: List[str]
    accepted_evidence: List[str]
    active_writers: List[str]
    dirty_worktrees: List[str]
    blocked_paths: List[str]
    human_decisions: List[str]
    next_executable_work: List[str]
    artifacts: List[str]
    safe_continuation_instructions: str
    
    def to_dict(self) -> dict:
        return asdict(self)

class HandoffValidationError(Exception):
    pass

def load_schema() -> dict:
    schema_path = Path(__file__).parent.parent / "courier_core" / "schemas" / "session_handoff.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found at {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))

def validate_handoff(handoff_dict: dict):
    schema = load_schema()
    try:
        jsonschema.validate(instance=handoff_dict, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        raise HandoffValidationError(f"Invalid handoff format: {e.message}")

def generate_handoff(handoff_data: SessionHandoff, output_path: str = None) -> str:
    """
    Generates a structured session handoff, validates it, and optionally writes it to a file.
    Returns the JSON string representation.
    """
    data = handoff_data.to_dict()
    validate_handoff(data)
    
    json_str = json.dumps(data, indent=2)
    if output_path:
        Path(output_path).write_text(json_str, encoding="utf-8")
        
    return json_str
