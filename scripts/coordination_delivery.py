from enum import Enum
import dataclasses
from typing import Optional
from scripts.coordination_ledger import AgentID, CoordinationEvent, EventType, MissionStatus

class NextActionType(str, Enum):
    WAIT = "WAIT"
    PREPARE_MISSION = "PREPARE_MISSION"
    DISCOVERABLE_CHECKPOINT_READY = "DISCOVERABLE_CHECKPOINT_READY"
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
        
        # We NO LONGER require Dennis to copy-paste.
        # We persist the payload/prompt as a discoverable payload so the agent can discover it upon wakeup.
        return NextAction(
            action_type=NextActionType.DISCOVERABLE_CHECKPOINT_READY,
            reason=f"Programmatic inbox unavailable for {agent_id}. Durable checkpoint persisted. Agent will discover on wakeup without human relay.",
            target_agent=agent_id,
            mission_id=mission_id,
            payload=prompt
        )

    def process_mission_request(self, agent_id: AgentID, mission_id: str, prompt: str) -> NextAction:
        return self.decide_delivery(agent_id, mission_id, prompt)

