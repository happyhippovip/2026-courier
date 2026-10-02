import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

@dataclass
class RecoveryReceipt:
    """
    Provider-neutral Recovery Receipt primitive.
    Cross-platform and atomic.
    """
    incident_id: str
    workkey: str
    host: str
    last_accepted_state: str
    failure_type: str
    surviving_work: List[str]
    recovery_action: str
    recovery_result: str
    evidence_refs: List[str]
    safe_resume_point: str
    data_loss_state: str
    timestamp: str = field(default_factory=utc_now)

    def validate(self) -> None:
        if not self.incident_id:
            raise ValueError("incident_id is required")
        if not self.workkey:
            raise ValueError("workkey is required")
        if not self.host:
            raise ValueError("host is required")
        if not self.failure_type:
            raise ValueError("failure_type is required")
        
        valid_results = {"SUCCESS", "FAILURE", "PARTIAL", "UNKNOWN"}
        if self.recovery_result.upper() not in valid_results:
            raise ValueError(f"recovery_result must be one of {valid_results}")
            
        valid_loss_states = {"NONE", "PARTIAL", "COMPLETE", "UNKNOWN"}
        if self.data_loss_state.upper() not in valid_loss_states:
            raise ValueError(f"data_loss_state must be one of {valid_loss_states}")

        if not isinstance(self.surviving_work, list):
            raise TypeError("surviving_work must be a list")
            
        if not isinstance(self.evidence_refs, list):
            raise TypeError("evidence_refs must be a list")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)

    def to_json(self) -> str:
        # Canonical JSON encoding (cross-platform, atomic-friendly)
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryReceipt":
        receipt = cls(**data)
        receipt.validate()
        return receipt

    @classmethod
    def from_json(cls, json_str: str) -> "RecoveryReceipt":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def write_atomic(self, path: str) -> None:
        """Write the receipt to disk atomically (cross-platform friendly)."""
        import os, tempfile
        json_data = self.to_json().encode('utf-8')
        dir_name = os.path.dirname(path) or "."
        fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".rcpt_tmp_")
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(json_data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
