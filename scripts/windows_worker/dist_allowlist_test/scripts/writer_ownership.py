from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import time

@dataclass
class WriterOwnershipRecord:
    scope: str
    writer_id: str
    workspace_path: str
    start_state_sha: str
    
    last_heartbeat: int
    dirty_files: List[str]
    handoff_state: str # e.g. "active", "pending_handoff", "released"
    
    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "WriterOwnershipRecord":
        return cls(**json.loads(json_str))

class WriterOwnershipManager:
    def __init__(self, stale_timeout_seconds: int = 300):
        self.stale_timeout_seconds = stale_timeout_seconds
        self._records: Dict[str, WriterOwnershipRecord] = {} # Keyed by workspace_path
        
    def acquire_ownership(self, scope: str, writer_id: str, workspace_path: str, start_state_sha: str, current_time: int) -> bool:
        """
        Attempts to acquire writer ownership for a workspace.
        Fails if another writer actively holds the lock and hasn't gone stale.
        """
        if workspace_path in self._records:
            existing_record = self._records[workspace_path]
            
            # If the current lock is active (not stale, not released)
            if existing_record.handoff_state != "released" and not self._is_stale(existing_record, current_time):
                # If it's already us, we can update the heartbeat
                if existing_record.writer_id == writer_id:
                    existing_record.last_heartbeat = current_time
                    return True
                return False # Held by someone else
                
        # Safe to acquire/steal
        self._records[workspace_path] = WriterOwnershipRecord(
            scope=scope,
            writer_id=writer_id,
            workspace_path=workspace_path,
            start_state_sha=start_state_sha,
            last_heartbeat=current_time,
            dirty_files=[],
            handoff_state="active"
        )
        return True
        
    def update_heartbeat(self, workspace_path: str, writer_id: str, current_time: int, dirty_files: List[str]):
        if workspace_path not in self._records or self._records[workspace_path].writer_id != writer_id:
            raise ValueError(f"Writer {writer_id} does not own {workspace_path}")
            
        record = self._records[workspace_path]
        record.last_heartbeat = current_time
        record.dirty_files = dirty_files
        
    def request_handoff(self, workspace_path: str, writer_id: str):
        if workspace_path not in self._records or self._records[workspace_path].writer_id != writer_id:
            raise ValueError(f"Writer {writer_id} does not own {workspace_path}")
            
        self._records[workspace_path].handoff_state = "pending_handoff"
        
    def release_ownership(self, workspace_path: str, writer_id: str):
        if workspace_path in self._records and self._records[workspace_path].writer_id == writer_id:
            self._records[workspace_path].handoff_state = "released"

    def _is_stale(self, record: WriterOwnershipRecord, current_time: int) -> bool:
        return (current_time - record.last_heartbeat) > self.stale_timeout_seconds
