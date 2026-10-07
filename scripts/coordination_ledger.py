import dataclasses
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class AgentID(str, Enum):
    GOOGLE_WINDOWS = "GOOGLE_WINDOWS"
    GOOGLE_MAC = "GOOGLE_MAC"
    CODEX_MAC = "CODEX_MAC"

class HostID(str, Enum):
    WINDOWS_REMOTE = "WINDOWS_REMOTE"
    MAC_LOCAL = "MAC_LOCAL"

class EventType(str, Enum):
    ASSIGNED = "ASSIGNED"
    STARTED = "STARTED"
    PARTIAL = "PARTIAL"
    FINAL = "FINAL"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"

class MissionStatus(str, Enum):
    WORKING = "WORKING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"

@dataclasses.dataclass
class CoordinationEvent:
    event_id: str
    mission_id: str
    agent_id: AgentID
    host_id: HostID
    event_type: EventType
    status: MissionStatus
    depends_on: List[str]
    head: Optional[str]
    evidence_ref: str
    created_at: str
    payload_hash: str

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)

class CoordinationReducer:
    def __init__(self):
        self.events: List[CoordinationEvent] = []
        self.missions: Dict[str, Dict] = {}
        self.processed_event_ids = set()

    def apply(self, event: CoordinationEvent):
        if event.event_id in self.processed_event_ids:
            return
        self.processed_event_ids.add(event.event_id)
        self.events.append(event)
        
        # Reducer logic to update mission state
        if event.mission_id not in self.missions:
            self.missions[event.mission_id] = {
                "mission_id": event.mission_id,
                "agent_id": event.agent_id,
                "host_id": event.host_id,
                "status": event.status,
                "depends_on": event.depends_on,
                "latest_event_id": event.event_id,
                "head": event.head,
                "evidence_ref": event.evidence_ref,
                "created_at": event.created_at,
                "updated_at": event.created_at,
            }
        else:
            mission = self.missions[event.mission_id]
            
            # State transition rules
            if event.event_type == EventType.ASSIGNED:
                mission["agent_id"] = event.agent_id
                mission["host_id"] = event.host_id
                mission["status"] = event.status
            elif event.event_type == EventType.STARTED:
                mission["status"] = MissionStatus.WORKING
            elif event.event_type == EventType.PARTIAL:
                # Doesn't close the mission, but updates evidence/head
                pass
            elif event.event_type == EventType.FINAL:
                mission["status"] = MissionStatus.DONE
            elif event.event_type == EventType.BLOCKED:
                mission["status"] = MissionStatus.BLOCKED
            elif event.event_type == EventType.ERROR:
                mission["status"] = MissionStatus.ERROR
            elif event.event_type == EventType.CANCELLED:
                mission["status"] = MissionStatus.ERROR # or CANCELLED if we add it
                
            mission["head"] = event.head or mission["head"]
            mission["evidence_ref"] = event.evidence_ref
            mission["updated_at"] = event.created_at
            mission["latest_event_id"] = event.event_id

    def get_mission(self, mission_id: str) -> Optional[Dict]:
        return self.missions.get(mission_id)
        
    def get_all_missions(self) -> Dict[str, Dict]:
        return self.missions
