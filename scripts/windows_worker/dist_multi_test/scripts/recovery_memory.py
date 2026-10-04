import json
from dataclasses import dataclass, asdict
from typing import List, Dict

@dataclass
class RecoveryCapability:
    fingerprint: str
    preconditions: List[str]
    safe_actions: List[str]
    forbidden_actions: List[str]
    verification: str
    fallback: str
    evidence_links: List[str]
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
        
    @classmethod
    def from_json(cls, json_str: str) -> "RecoveryCapability":
        return cls(**json.loads(json_str))

class RecoveryMemoryStore:
    def __init__(self):
        self._capabilities: Dict[str, RecoveryCapability] = {}
        
    def register(self, capability: RecoveryCapability):
        self._capabilities[capability.fingerprint] = capability
        
    def get_capability(self, fingerprint: str) -> RecoveryCapability:
        if fingerprint not in self._capabilities:
            raise KeyError(f"No proven recovery capability for fingerprint: {fingerprint}. Do not generalize automatically.")
        return self._capabilities[fingerprint]

