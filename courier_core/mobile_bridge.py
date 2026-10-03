from dataclasses import dataclass
from typing import Dict, Any, Optional
from courier_core.customer_status import CustomerStatus

@dataclass
class BridgePayload:
    transaction_id: str
    status: CustomerStatus
    safe_message: str
    action_required: bool
    context: Dict[str, Any]

class MobileBridgeContract:
    @staticmethod
    def construct_sync_payload(tx_id: str, status: CustomerStatus, needs_auth: bool = False) -> BridgePayload:
        if status == CustomerStatus.NEEDS_YOU:
            return BridgePayload(
                transaction_id=tx_id,
                status=status,
                safe_message="Courier requires your attention to proceed.",
                action_required=True,
                context={"auth_needed": needs_auth}
            )
        elif status == CustomerStatus.RECOVERING:
            return BridgePayload(
                transaction_id=tx_id,
                status=status,
                safe_message="Courier is repairing a technical issue.",
                action_required=False,
                context={}
            )
        else:
            return BridgePayload(
                transaction_id=tx_id,
                status=status,
                safe_message="Courier is operating normally.",
                action_required=False,
                context={}
            )
