from enum import Enum
import dataclasses
from typing import Optional
from scripts.coordination_ledger import AgentID, CoordinationEvent, EventType, MissionStatus

class NextActionType(str, Enum):
    WAIT = "WAIT"
    PREPARE_MISSION = "PREPARE_MISSION"
    HUMAN_DELIVERY_REQUIRED = "HUMAN_DELIVERY_REQUIRED"
    RECONCILE = "RECONCILE"
    CANCEL_REQUIRED = "CANCEL_REQUIRED"
    INTEGRATE_RESULTS = "INTEGRATE_RESULTS"
    HUMAN_ACTION_REQUIRED = "HUMAN_ACTION_REQUIRED"

@dataclasses.dataclass
class NextAction:
    action_type: NextActionType
    reason: str
    target_agent: Optional[AgentID] = None
    mission_id: Optional[str] = None
    payload: Optional[str] = None

class CoordinationDelivery:
    def __init__(self):
        # Programmatic inboxes will be mapped here later (P8 Courier integration)
        self.supported_inboxes = {}

    def decide_delivery(self, agent_id: AgentID, mission_id: str, prompt: str) -> NextAction:
        if agent_id in self.supported_inboxes:
            # Here we would dispatch to the programmatic inbox
            pass
        
        # Default for unsupported inboxes
        return NextAction(
            action_type=NextActionType.HUMAN_DELIVERY_REQUIRED,
            reason=f"Agent {agent_id} has no programmatic inbox. Human copy/paste required.",
            target_agent=agent_id,
            mission_id=mission_id,
            payload=prompt
        )

    def process_mission_request(self, agent_id: AgentID, mission_id: str, prompt: str) -> NextAction:
        return self.decide_delivery(agent_id, mission_id, prompt)

