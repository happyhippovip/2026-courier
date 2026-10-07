from scripts.coordination_delivery import CoordinationDelivery, NextActionType
from scripts.coordination_ledger import AgentID

def test_coordination_delivery_unsupported():
    delivery = CoordinationDelivery()
    action = delivery.decide_delivery(
        agent_id=AgentID.GOOGLE_WINDOWS,
        mission_id="m123",
        prompt="Please implement feature X"
    )
    
    assert action.action_type == NextActionType.HUMAN_DELIVERY_REQUIRED
    assert action.target_agent == AgentID.GOOGLE_WINDOWS
    assert action.mission_id == "m123"
    assert action.payload == "Please implement feature X"
    assert "no programmatic inbox" in action.reason
