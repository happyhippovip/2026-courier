from __future__ import annotations
import enum
import json
import os
import fcntl
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional

class CapitalLayer(enum.Enum):
    PAPER_RESEARCH = 'PAPER_RESEARCH'
    MICRO_CANARY = 'MICRO_CANARY'
    SMALL_LIVE = 'SMALL_LIVE'
    LIVE_100K = 'LIVE_100K'
    LIVE_600K = 'LIVE_600K'

@dataclass
class ReservationResult:
    status: str
    reservation_id: Optional[str]
    amount_eur: float
    message: str

@dataclass
class LayerAuthResult:
    authorized: bool
    layer: CapitalLayer
    reason: str

@dataclass
class BreakerResult:
    status: str
    tripped_reason: Optional[str]

@dataclass
class CooldownResult:
    active: bool
    cooldown_until: Optional[datetime]

@dataclass
class CircuitBreaker:
    per_trade_loss_limit: float
    session_loss_limit: float
    global_budget_limit: float
    consecutive_loss_limit: int
    unknown_execution_limit: int

@dataclass
class LossEvent:
    event_id: str
    timestamp: str
    amount: float
    instrument: str
    cooldown_required: bool
    cooldown_until: Optional[str]

@dataclass
class BlastRadiusEnvelope:
    treasury_total: float
    trading_reserve: float
    execution_allocation: float
    agent_envelope: float

class CapitalFirewall:
    GLOBAL_CANARY_BUDGET_EUR = 35.0
    MAX_SINGLE_CANARY_LOSS_EUR = 2.0
    STATE_FILE = 'events/market-defense/capital_state.json'

    def __init__(self, state_file: str = None):
        if state_file:
            self.state_file = state_file
        else:
            self.state_file = os.path.join(os.getcwd(), self.STATE_FILE)
            
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        if not os.path.exists(self.state_file):
            self._init_state()

    def _init_state(self):
        state = {
            "budget_used": 0.0,
            "reservations": {},
            "loss_events": []
        }
        self._write_state(state)

    def _read_state(self) -> dict:
        if not os.path.exists(self.state_file):
            self._init_state()
        with open(self.state_file, 'r') as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _write_state(self, state: dict):
        tmp_file = f"{self.state_file}.tmp.{uuid.uuid4().hex}"
        with open(tmp_file, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_file, self.state_file)

    def reserve_budget(self, amount_eur: float, agent_id: str) -> ReservationResult:
        if amount_eur > self.MAX_SINGLE_CANARY_LOSS_EUR:
            return ReservationResult("DENIED", None, amount_eur, f"Exceeds max single loss {self.MAX_SINGLE_CANARY_LOSS_EUR}")

        if not os.path.exists(self.state_file):
            self._init_state()

        with open(self.state_file, 'a+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            try:
                state = json.load(f)
            except json.JSONDecodeError:
                state = {"budget_used": 0.0, "reservations": {}, "loss_events": []}
            
            total_allocated = state.get("budget_used", 0.0) + sum(res["amount"] for res in state.get("reservations", {}).values())
            
            if total_allocated + amount_eur > self.GLOBAL_CANARY_BUDGET_EUR:
                fcntl.flock(f, fcntl.LOCK_UN)
                return ReservationResult("BUDGET_EXHAUSTED", None, amount_eur, "Global budget limit reached")
                
            res_id = str(uuid.uuid4())
            state.setdefault("reservations", {})[res_id] = {
                "agent_id": agent_id,
                "amount": amount_eur,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            f.seek(0)
            f.truncate()
            json.dump(state, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)
            
        return ReservationResult("APPROVED", res_id, amount_eur, "Budget reserved")

    def release_reservation(self, reservation_id: str, actual_pnl_eur: float):
        with open(self.state_file, 'a+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            try:
                state = json.load(f)
            except json.JSONDecodeError:
                state = {"budget_used": 0.0, "reservations": {}, "loss_events": []}
            
            if reservation_id in state.get("reservations", {}):
                res = state["reservations"].pop(reservation_id)
                if actual_pnl_eur < 0:
                    state["budget_used"] = state.get("budget_used", 0.0) + abs(actual_pnl_eur)
                    
            f.seek(0)
            f.truncate()
            json.dump(state, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)

    def get_remaining_budget(self) -> float:
        state = self._read_state()
        used = state.get("budget_used", 0.0)
        reserved = sum(res["amount"] for res in state.get("reservations", {}).values())
        return max(0.0, self.GLOBAL_CANARY_BUDGET_EUR - (used + reserved))

    def check_layer_authorization(self, layer: CapitalLayer) -> LayerAuthResult:
        if layer == CapitalLayer.PAPER_RESEARCH:
            return LayerAuthResult(True, layer, "Auto-authorized")
        return LayerAuthResult(False, layer, "Human approval required")

    def check_circuit_breakers(self, proposed_loss: float, session_losses: List[float]) -> BreakerResult:
        cb = CircuitBreaker(
            per_trade_loss_limit=self.MAX_SINGLE_CANARY_LOSS_EUR,
            session_loss_limit=10.0,
            global_budget_limit=self.GLOBAL_CANARY_BUDGET_EUR,
            consecutive_loss_limit=3,
            unknown_execution_limit=1
        )
        if proposed_loss > cb.per_trade_loss_limit:
            return BreakerResult("TRIPPED", "Per trade loss limit exceeded")
        if sum(session_losses) + proposed_loss > cb.session_loss_limit:
            return BreakerResult("TRIPPED", "Session loss limit exceeded")
        if len(session_losses) >= cb.consecutive_loss_limit:
            return BreakerResult("TRIPPED", "Consecutive loss limit reached")
            
        return BreakerResult("PASS", None)

    def check_cooldown(self, instrument: str) -> CooldownResult:
        state = self._read_state()
        now = datetime.now(timezone.utc)
        for ev in state.get("loss_events", []):
            if ev.get("instrument") == instrument and ev.get("cooldown_required"):
                until_str = ev.get("cooldown_until")
                if until_str:
                    until_dt = datetime.fromisoformat(until_str)
                    if now < until_dt:
                        return CooldownResult(True, until_dt)
        return CooldownResult(False, None)

    def detect_martingale(self, recent_trades: List[Dict]) -> bool:
        if len(recent_trades) < 2:
            return False
        last_trade = recent_trades[-1]
        prev_trade = recent_trades[-2]
        
        if prev_trade.get("pnl", 0) < 0 and last_trade.get("size", 0) > prev_trade.get("size", 0):
            return True
        return False
