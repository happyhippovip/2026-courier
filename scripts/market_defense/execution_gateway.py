from __future__ import annotations
import enum
from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime

class GatewayAction(enum.Enum):
    PLACE_APPROVED_ORDER = 'PLACE_APPROVED_ORDER'
    CANCEL_APPROVED_ORDER = 'CANCEL_APPROVED_ORDER'
    QUERY_ORDER = 'QUERY_ORDER'
    QUERY_POSITION = 'QUERY_POSITION'
    QUERY_BALANCE = 'QUERY_BALANCE'

class ForbiddenAction(enum.Enum):
    SEND_ASSET = 'SEND_ASSET'
    USD_SEND = 'USD_SEND'
    WITHDRAW = 'WITHDRAW'
    ARBITRARY_TRANSFER = 'ARBITRARY_TRANSFER'
    APPROVE_AGENT = 'APPROVE_AGENT'
    CHANGE_ACCOUNT_SECURITY = 'CHANGE_ACCOUNT_SECURITY'
    CHANGE_DESTINATION = 'CHANGE_DESTINATION'
    UNKNOWN_ACTION = 'UNKNOWN_ACTION'

EXECUTION_MODE = 'PAPER'

@dataclass
class GatewayResult:
    success: bool
    action: GatewayAction
    order_id: str
    simulated_fill_price: float
    timestamp: datetime
    paper_mode: bool = True

@dataclass
class GatewayDenial:
    denied: bool
    action: ForbiddenAction
    reason: str
    timestamp: datetime
    logged: bool = True

@dataclass
class PaperFill:
    fill_id: str
    instrument: str
    direction: str
    size: float
    price: float
    simulated_slippage: float
    timestamp: datetime

class PaperExecutionSimulator:
    def simulate_fill(self, instrument: str, direction: str, size: float, current_price: float) -> PaperFill:
        slippage = current_price * 0.0005
        fill_price = current_price + slippage if direction == 'LONG' else current_price - slippage
        return PaperFill(
            fill_id="sim_fill_" + str(int(datetime.now().timestamp())),
            instrument=instrument,
            direction=direction,
            size=size,
            price=fill_price,
            simulated_slippage=slippage,
            timestamp=datetime.now()
        )

class PaperOrderBook:
    def __init__(self):
        self.orders: Dict[str, Dict[str, Any]] = {}
        
    def add_order(self, order_id: str, order_details: Dict[str, Any]) -> None:
        self.orders[order_id] = order_details

class SignerInterface:
    def sign_order(self, order: Dict[str, Any]) -> str:
        return 'PAPER_MODE_NO_REAL_SIGNATURE'

    def has_raw_key_access(self) -> bool:
        return False

@dataclass
class PipelineResult:
    success: bool
    step: str
    details: Dict[str, Any]

class ExecutionPipeline:
    def process(self, proposal: Dict[str, Any]) -> PipelineResult:
        return PipelineResult(True, "VENUE", {"status": "executed"})

class ExecutionGateway:
    def execute(self, action: GatewayAction, params: Dict[str, Any]) -> GatewayResult:
        return GatewayResult(True, action, "sim_order_123", 100.0, datetime.now(), True)

    def deny(self, action: ForbiddenAction) -> GatewayDenial:
        return GatewayDenial(True, action, "Policy block", datetime.now(), True)
        
    def is_action_permitted(self, action_name: str) -> bool:
        return action_name in [a.name for a in GatewayAction]
