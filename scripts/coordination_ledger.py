import dataclasses
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class AgentID(str, Enum):
    GOOGLE_WINDOWS = "GOOGLE_WINDOWS"
    GOOGLE_MAC = "GOOGLE_MAC"
    CODEX_MAC = "CODEX_MAC"
    UNKNOWN = "UNKNOWN"

class HostID(str, Enum):
    WINDOWS_REMOTE = "WINDOWS_REMOTE"
    MAC_LOCAL = "MAC_LOCAL"
    UNKNOWN = "UNKNOWN"

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
    branch: Optional[str] = None
    pr: Optional[str] = None
    test_evidence: Optional[str] = None
    blocker: Optional[str] = None
    next_action: Optional[str] = None
    ownership: Optional[str] = None

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
        # 4. duplicate/replayed event has no duplicate effect
        if event.event_id in self.processed_event_ids:
            return
            
        self.processed_event_ids.add(event.event_id)
        self.events.append(event)
        
        # 9. unknown authority fails closed
        if event.agent_id == AgentID.UNKNOWN or event.host_id == HostID.UNKNOWN:
            # We log the event but do not mutate state
            return
        
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
                "branch": event.branch,
                "pr": event.pr,
                "test_evidence": event.test_evidence,
                "blocker": event.blocker,
                "next_action": event.next_action,
                "ownership": event.ownership or event.agent_id.value
            }
        else:
            mission = self.missions[event.mission_id]
            
            # 5. stale checkpoint cannot overwrite newer progress
            if event.created_at < mission["updated_at"]:
                return
                
            # 6. conflicting writer ownership fails safely
            # If the mission is actively owned by someone else, we reject mutations unless reassigned
            current_owner = mission.get("ownership")
            new_owner = event.ownership or event.agent_id.value
            if current_owner and current_owner != new_owner and event.event_type not in (EventType.ASSIGNED, EventType.CANCELLED):
                # Cannot mutate unless specifically re-assigned
                return
            
            # State transition rules
            if event.event_type == EventType.ASSIGNED:
                mission["agent_id"] = event.agent_id
                mission["host_id"] = event.host_id
                mission["status"] = event.status
                mission["ownership"] = new_owner
            elif event.event_type == EventType.STARTED:
                mission["status"] = MissionStatus.WORKING
            elif event.event_type == EventType.PARTIAL:
                # 3. PARTIAL checkpoint remains resumable (status remains WORKING)
                mission["status"] = MissionStatus.WORKING
            elif event.event_type == EventType.FINAL:
                mission["status"] = MissionStatus.DONE
                mission["ownership"] = None # Released!
            elif event.event_type == EventType.BLOCKED:
                mission["status"] = MissionStatus.BLOCKED
            elif event.event_type == EventType.ERROR:
                mission["status"] = MissionStatus.ERROR
            elif event.event_type == EventType.CANCELLED:
                mission["status"] = MissionStatus.ERROR
                mission["ownership"] = None
                
            mission["head"] = event.head or mission["head"]
            mission["evidence_ref"] = event.evidence_ref
            mission["branch"] = event.branch or mission.get("branch")
            mission["pr"] = event.pr or mission.get("pr")
            mission["test_evidence"] = event.test_evidence or mission.get("test_evidence")
            mission["blocker"] = event.blocker or mission.get("blocker")
            mission["next_action"] = event.next_action or mission.get("next_action")
            
            mission["updated_at"] = event.created_at
            mission["latest_event_id"] = event.event_id

    def get_mission(self, mission_id: str) -> Optional[Dict]:
        return self.missions.get(mission_id)
        
    def get_all_missions(self) -> Dict[str, Dict]:
        return self.missions

