import json
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class IncidentMemoryRecord:
    incident_id: str
    
    # 1. Symptom: What was originally seen/reported?
    symptom: str
    
    # 2. Observation: What was actually measured/seen by monitoring systems?
    observation: str
    
    # 3. Agent Report: What did the local agent report before/during the crash?
    agent_report: str
    
    # 4. Verified Evidence: Log files, hashes, physical traces that back up the observation
    verified_evidence: List[str]
    
    # 5. Root Cause Hypothesis: Initial thoughts on what went wrong
    root_cause_hypothesis: str
    
    # 6. Confirmed Root Cause: What was actually proven to be the issue
    confirmed_root_cause: str
    
    # 7. Recovery: The specific patch/fix/procedure used to resolve it
    recovery: str
    
    # 8. Counter-Test: The test built to prevent regressions
    counter_test: str
    
    # 9. Remaining Uncertainty: What is still unknown or unproven?
    remaining_uncertainty: str
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "IncidentMemoryRecord":
        return cls(**json.loads(json_str))
