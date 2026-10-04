import json
import os
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Optional

class CheckpointState(str, Enum):
    PLANNED = "planned"
    STARTED = "started"
    MODIFIED = "modified"
    TESTED = "tested"
    VERIFIED = "verified"
    COMMITTED = "committed"
    PUSHED = "pushed"
    LANDED = "landed"

@dataclass
class TaskCheckpoint:
    workkey: str
    state: CheckpointState
    context: Dict[str, str]
    
    def to_dict(self) -> dict:
        return {
            "workkey": self.workkey,
            "state": self.state.value,
            "context": self.context
        }

class CheckpointManager:
    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_path(self, workkey: str) -> Path:
        # Simple file-based durability for Windows worker
        return self.storage_dir / f"{workkey}.checkpoint.json"
        
    def save_checkpoint(self, checkpoint: TaskCheckpoint):
        path = self._get_path(checkpoint.workkey)
        
        # Write to temp file then rename for atomicity (crash resistance)
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno()) # Force to disk
            
        temp_path.replace(path)
        
    def load_checkpoint(self, workkey: str) -> Optional[TaskCheckpoint]:
        path = self._get_path(workkey)
        if not path.exists():
            return None
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return TaskCheckpoint(
            workkey=data["workkey"],
            state=CheckpointState(data["state"]),
            context=data["context"]
        )

def determine_recovery_action(checkpoint: TaskCheckpoint) -> str:
    """
    Given a loaded checkpoint after a crash, determine what the agent must do to recover.
    Does not treat 'started' as 'completed'.
    """
    state = checkpoint.state
    if state == CheckpointState.PLANNED:
        return "Begin execution."
    elif state == CheckpointState.STARTED:
        return "Clean up partial work and restart from the beginning."
    elif state == CheckpointState.MODIFIED:
        return "Run tests to verify the uncommitted modifications."
    elif state == CheckpointState.TESTED:
        return "Review test evidence and transition to verified if passing."
    elif state == CheckpointState.VERIFIED:
        return "Commit the verified changes."
    elif state == CheckpointState.COMMITTED:
        return "Push the committed changes to remote."
    elif state == CheckpointState.PUSHED:
        return "Wait for landing/merge validation."
    elif state == CheckpointState.LANDED:
        return "Work is fully completed."
    
    return "Unknown state."
