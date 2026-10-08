import dataclasses
from typing import List, Optional, Dict
from datetime import datetime, timezone
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


def _coerce_authority(enum_cls, value):
    """Unknown/unlisted authority collapses to UNKNOWN so the reducer fails closed."""
    try:
        return enum_cls(value)
    except ValueError:
        return enum_cls.UNKNOWN


def parse_timestamp(value) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp into an aware UTC datetime; None if unparseable."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None  # Naive timestamps are ambiguous across hosts: fail closed.
    return parsed.astimezone(timezone.utc)


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
        data = dataclasses.asdict(self)
        for key in ("agent_id", "host_id", "event_type", "status"):
            value = data[key]
            data[key] = value.value if isinstance(value, Enum) else value
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Rebuild an event from durable JSON (e.g. a fresh process reading shared truth).

        Unknown agent/host become UNKNOWN (fail closed in the reducer).  Unknown
        event types / statuses or unknown fields raise ValueError so callers skip them.
        """
        known = {f.name for f in dataclasses.fields(cls)}
        unknown_fields = set(data) - known
        if unknown_fields:
            raise ValueError(f"Unknown coordination event fields: {sorted(unknown_fields)}")
        payload = dict(data)
        payload["agent_id"] = _coerce_authority(AgentID, payload.get("agent_id"))
        payload["host_id"] = _coerce_authority(HostID, payload.get("host_id"))
        payload["event_type"] = EventType(payload.get("event_type"))
        payload["status"] = MissionStatus(payload.get("status"))
        payload["depends_on"] = list(payload.get("depends_on") or [])
        return cls(**payload)


class CoordinationReducer:
    def __init__(self, lease_ttl_s: Optional[float] = 1800.0):
        self.lease_ttl_s = lease_ttl_s
        self.events: List[CoordinationEvent] = []
        self.missions: Dict[str, Dict] = {}
        self.processed_event_ids = set()

    def apply(self, event: CoordinationEvent) -> bool:
        """Apply an event. Returns True only if it mutated mission state."""
        # 4. duplicate/replayed event has no duplicate effect
        if event.event_id in self.processed_event_ids:
            return False

        self.processed_event_ids.add(event.event_id)
        self.events.append(event)

        # 9. unknown authority fails closed
        if event.agent_id == AgentID.UNKNOWN or event.host_id == HostID.UNKNOWN:
            # We log the event but do not mutate state
            return False

        event_ts = parse_timestamp(event.created_at)
        if event_ts is None:
            return False  # Unordered events cannot be trusted against newer progress.

        new_owner = event.ownership or event.agent_id.value

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
                "ownership": None if event.event_type in (EventType.FINAL, EventType.CANCELLED) else new_owner,
            }
            return True

        mission = self.missions[event.mission_id]

        # 5. stale checkpoint cannot overwrite newer progress
        if event_ts < parse_timestamp(mission["updated_at"]):
            return False

        # 6. conflicting writer ownership fails safely
        current_owner = mission.get("ownership")
        if current_owner and current_owner != new_owner:
            if event.event_type == EventType.ASSIGNED:
                # Reassignment of a live owned mission is only allowed after ERROR.
                if mission["status"] != MissionStatus.ERROR:
                    return False
            elif event.event_type == EventType.CANCELLED:
                # A non-owner may only cancel if the lease has expired.
                last_ts = parse_timestamp(mission["updated_at"])
                if (
                    self.lease_ttl_s is not None
                    and last_ts is not None
                    and (event_ts - last_ts).total_seconds() < self.lease_ttl_s
                ):
                    return False
            else:
                return False

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
        return True

    def get_mission(self, mission_id: str) -> Optional[Dict]:
        return self.missions.get(mission_id)

    def get_all_missions(self) -> Dict[str, Dict]:
        return self.missions
