from courier_core.mobile_bridge import MobileBridgeContract
from courier_core.customer_status import CustomerStatus

def test_bridge_payload_working():
    payload = MobileBridgeContract.construct_sync_payload("tx1", CustomerStatus.WORKING)
    assert not payload.action_required
    assert payload.safe_message == "Courier is operating normally."

def test_bridge_payload_needs_you():
    payload = MobileBridgeContract.construct_sync_payload("tx2", CustomerStatus.NEEDS_YOU, needs_auth=True)
    assert payload.action_required
    assert payload.context["auth_needed"] is True
