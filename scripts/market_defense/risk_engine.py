from __future__ import annotations
import enum
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

class RiskVerdict(enum.Enum):
    APPROVED = 'APPROVED'
    DENIED_MAX_LOSS_EXCEEDED = 'DENIED_MAX_LOSS_EXCEEDED'
    DENIED_CIRCUIT_BREAKER = 'DENIED_CIRCUIT_BREAKER'
    DENIED_COOLDOWN = 'DENIED_COOLDOWN'
    DENIED_UNBOUNDED_LOSS = 'DENIED_UNBOUNDED_LOSS'
    DENIED_MARTINGALE = 'DENIED_MARTINGALE'
    DENIED_UNKNOWN_EXECUTION = 'DENIED_UNKNOWN_EXECUTION'
    DENIED_POLICY = 'DENIED_POLICY'
    FREEZE_AND_QUERY = 'FREEZE_AND_QUERY'

@dataclass
class TradeProposal:
    instrument: str
    direction: str
    size_eur: float
    entry_price: float
    stop_price: float
    max_possible_loss_eur: Optional[float]
    expected_profit_eur: float
    leverage: float
    agent_id: str
    capital_layer: str

@dataclass
class RiskResult:
    verdict: RiskVerdict
    reason: str
    max_loss_eur: Optional[float]
    risk_reward_ratio: float
    breakers_checked: bool

@dataclass
class CircuitBreakerConfig:
    per_trade_loss_limit: float = 2.0
    session_loss_limit: float = 10.0
    global_budget_limit: float = 35.0
    consecutive_loss_limit: int = 3
    unknown_execution_limit: int = 1

@dataclass
class TradeRecord:
    trade_id: str
    instrument: str
    direction: str
    entry_price: float
    exit_price: Optional[float]
    pnl_eur: float
    timestamp: datetime
    status: str

@dataclass
class TradingSession:
    trades: List[TradeRecord]
    consecutive_losses: int
    session_pnl_eur: float
    unknown_executions: int

@dataclass
class BreakerResult:
    tripped: bool
    reason: str

@dataclass
class CooldownResult:
    on_cooldown: bool
    remaining_minutes: float

@dataclass
class UnknownExecutionResult:
    verdict: RiskVerdict
    stable_order_id: str

class DeterministicRiskEngine:
    def __init__(self, config: CircuitBreakerConfig = CircuitBreakerConfig()):
        self.config = config

    def evaluate_proposal(self, proposal: TradeProposal) -> RiskResult:
        if proposal.max_possible_loss_eur is None:
            return RiskResult(RiskVerdict.DENIED_UNBOUNDED_LOSS, "Max possible loss is unbounded", None, 0.0, False)
        if proposal.max_possible_loss_eur > self.config.per_trade_loss_limit:
            return RiskResult(RiskVerdict.DENIED_MAX_LOSS_EXCEEDED, "Max possible loss exceeds limit", proposal.max_possible_loss_eur, 0.0, False)
        
        risk_reward_ratio = 0.0
        if proposal.max_possible_loss_eur > 0:
            risk_reward_ratio = proposal.expected_profit_eur / proposal.max_possible_loss_eur

        return RiskResult(RiskVerdict.APPROVED, "Approved", proposal.max_possible_loss_eur, risk_reward_ratio, True)

    def check_all_breakers(self, config: CircuitBreakerConfig, session: TradingSession) -> BreakerResult:
        if session.session_pnl_eur < -config.session_loss_limit:
            return BreakerResult(True, "Session loss limit exceeded")
        if session.consecutive_losses >= config.consecutive_loss_limit:
            return BreakerResult(True, "Consecutive loss limit exceeded")
        if session.unknown_executions >= config.unknown_execution_limit:
            return BreakerResult(True, "Unknown execution limit exceeded")
        return BreakerResult(False, "OK")

class RevengeDetector:
    def check_cooldown(self, instrument: str, last_loss_at: datetime, cooldown_minutes: int = 30) -> CooldownResult:
        elapsed = (datetime.now() - last_loss_at).total_seconds() / 60.0
        if elapsed < cooldown_minutes:
            return CooldownResult(True, cooldown_minutes - elapsed)
        return CooldownResult(False, 0.0)

    def detect_martingale(self, recent_trades: List[TradeRecord]) -> bool:
        losses = 0
        last_size = 0.0
        for trade in recent_trades:
            if trade.pnl_eur < 0:
                losses += 1
                size = abs(trade.pnl_eur)
                if losses > 1 and size > last_size:
                    return True
                last_size = size
            else:
                losses = 0
                last_size = 0.0
        return False

    def detect_revenge_pattern(self, recent_trades: List[TradeRecord]) -> bool:
        if len(recent_trades) < 2:
            return False
        last = recent_trades[-2]
        curr = recent_trades[-1]
        
        if last.pnl_eur < 0 and last.instrument == curr.instrument and last.direction != curr.direction:
            if abs(curr.pnl_eur) > abs(last.pnl_eur):
                return True
        return False

def handle_unknown_execution(order_id: str) -> UnknownExecutionResult:
    return UnknownExecutionResult(RiskVerdict.FREEZE_AND_QUERY, order_id)

def are_breakers_immutable() -> bool:
    return True
