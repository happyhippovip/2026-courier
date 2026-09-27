import json
import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path

VALID_EVENT_TYPES = {
    "GOAL_CREATED",
    "TASK_QUEUED",
    "TASK_DISPATCHED",
    "WORK_STARTED",
    "RESULT_READY",
    "RESULT_RECEIVED",
    "VERIFICATION_PASS",
    "VERIFICATION_FAIL",
    "TASK_RECONCILED",
    "TASK_FAILED",
    "HUMAN_REQUIRED",
    "RETRY_CREATED",
    "RECOVERY",
    "NEXT_RELEASED",
    "GOAL_DONE"
}

class LedgerError(Exception):
    pass

class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.parent:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        
    def _hash_record(self, record: Dict[str, Any]) -> str:
        # Create deterministic hash excluding the hash field itself
        record_copy = record.copy()
        record_copy.pop("event_hash", None)
        canonical = json.dumps(record_copy, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def validate_event(self, record: Dict[str, Any]) -> bool:
        required = ["schema_version", "event_id", "timestamp", "event_type", "goal_id", "event_hash"]
        if not all(k in record for k in required):
            return False
        if record["event_type"] not in VALID_EVENT_TYPES:
            return False
        
        # Verify integrity
        expected_hash = self._hash_record(record)
        return record["event_hash"] == expected_hash

    def append_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if "event_type" not in event or event["event_type"] not in VALID_EVENT_TYPES:
            raise LedgerError(f"Invalid or missing event_type: {event.get('event_type')}")
        if "goal_id" not in event:
            raise LedgerError("Missing required field: goal_id")

        event_id = event.get("event_id") or str(uuid.uuid4())
        timestamp = event.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        record = {
            "schema_version": "ledger-event-1.0",
            "event_id": event_id,
            "timestamp": timestamp,
        }
        record.update(event)
        
        record["event_hash"] = self._hash_record(record)
        
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
        return record

    def read_events(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        if self.validate_event(record):
                            events.append(record)
                    except json.JSONDecodeError:
                        pass # Skip malformed lines for now, or could raise
        return events

    def events_for_goal(self, goal_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.read_events() if e.get("goal_id") == goal_id]

    def events_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.read_events() if e.get("task_id") == task_id]

    def latest_event(self, goal_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        events = self.events_for_goal(goal_id) if goal_id else self.read_events()
        return events[-1] if events else None

