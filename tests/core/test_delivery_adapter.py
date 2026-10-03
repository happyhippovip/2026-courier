from courier_core.delivery_state import DeliveryStateMachine, DeliveryState
from courier_core.adapter_interface import BaseProviderAdapter
from typing import Dict, Any

class MockDeterministicAdapter(BaseProviderAdapter):
    def connect(self) -> bool:
        return True
        
    def execute_action(self, action_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action_name == "crash":
            raise ValueError("Deterministic crash")
        return {"status": "ok", "payload_echo": payload}
        
    def verify_side_effect(self, action_name: str, payload: Dict[str, Any]) -> bool:
        return action_name != "crash"

def test_delivery_state_machine():
    fsm = DeliveryStateMachine()
    assert fsm.state == DeliveryState.APPROVED
    
    assert fsm.transition(DeliveryState.PLANNED)
    assert fsm.transition(DeliveryState.AUTHORIZED)
    assert fsm.transition(DeliveryState.EXECUTING)
    
    # Cannot jump to delivered directly from executing
    assert not fsm.transition(DeliveryState.DELIVERED)
    assert fsm.state == DeliveryState.EXECUTING
    
    assert fsm.transition(DeliveryState.VERIFYING)
    assert fsm.transition(DeliveryState.DELIVERED)

def test_adapter_contract():
    adapter = MockDeterministicAdapter()
    assert adapter.connect() is True
    
    res = adapter.execute_action("test", {"key": "value"})
    assert res["status"] == "ok"
    
    assert adapter.verify_side_effect("test", {"key": "value"}) is True
