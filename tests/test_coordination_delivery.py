from scripts.coordination_delivery import CoordinationDelivery, NextActionType, AgentID

def test_coordination_delivery_unsupported():
    delivery = CoordinationDelivery()
    action = delivery.decide_delivery(
        agent_id=AgentID.GOOGLE_WINDOWS,
        mission_id="m123",
        prompt="Please implement feature X"
    )

    assert action.action_type == NextActionType.DISCOVERABLE_CHECKPOINT_READY
    assert action.target_agent == AgentID.GOOGLE_WINDOWS
    assert action.mission_id == "m123"
    assert action.payload == "Please implement feature X"
    assert "Durable checkpoint persisted" in action.reason
