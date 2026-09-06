from __future__ import annotations
import enum
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

class DislocationKind(enum.Enum):
    PRICE = 'PRICE_DISLOCATION'
    LIQUIDITY = 'LIQUIDITY_DISLOCATION'
    FUNDING = 'FUNDING_DISLOCATION'
    OPEN_INTEREST = 'OPEN_INTEREST_DISLOCATION'
    VOLATILITY = 'VOLATILITY_SPIKE'
    CROSS_VENUE = 'CROSS_VENUE_DISAGREEMENT'
    NEWS = 'NEWS_SHOCK'
    LIQUIDATION = 'LIQUIDATION_CASCADE'

class TradeVerdict(enum.Enum):
    NO_TRADE = 'NO_TRADE'
    WATCH = 'WATCH'
    MICRO_CANARY_CANDIDATE = 'MICRO_CANARY_CANDIDATE'
    BLOCKED = 'BLOCKED'

@dataclass
class DislocationEvent:
    event_id: str
    kind: DislocationKind
    start_time: datetime
    price_before: float
    price_low: float
    price_high: float
    max_drawdown_pct: float
    max_rally_pct: float
    spread: float
    liquidity_score: float
    funding_rate: float
    oi_change_pct: float
    news_context: str
    recovery_time_seconds: float
    false_signal_risk: float

@dataclass
class MarketSnapshot:
    timestamp: datetime
    price: float
    price_1h_ago: float
    price_24h_ago: float
    spread: float
    bid_depth: float
    ask_depth: float
    funding_rate: float
    open_interest: float
    open_interest_1h_ago: float
    volume_24h: float
    volatility_1h: float
    liquidations_1h: float

@dataclass
class CandidateScore:
    market_structure: float
    volatility: float
    liquidity: float
    spread: float
    open_interest: float
    funding: float
    liquidation_risk: float
    news_shock: float
    data_confidence: float
    crowding: float
    execution_cost: float
    risk_reward: float
    event_risk: float

@dataclass
class StopHuntAlert:
    detected: bool
    conditions: List[str]
    recommendation: str

class BtcDislocationEngine:
    BTC_DEFAULT_LEVERAGE = 0

    def detect_dislocations(self, market_snapshot: MarketSnapshot) -> List[DislocationEvent]:
        return []

    def score_candidate(self, direction: str, snapshot: MarketSnapshot, events: List[DislocationEvent]) -> CandidateScore:
        return CandidateScore(
            0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5
        )

    def evaluate(self, snapshot: MarketSnapshot) -> TradeVerdict:
        return TradeVerdict.NO_TRADE

    def detect_stop_hunt_conditions(self, snapshot: MarketSnapshot) -> StopHuntAlert:
        conditions = []
        if snapshot.spread > 0.05:
            conditions.append("Sudden spread expansion (>2x normal)")
        if snapshot.bid_depth < 1.0 or snapshot.ask_depth < 1.0:
            conditions.append("Depth collapse (>50% drop)")
        if snapshot.liquidations_1h > 1000000:
            conditions.append("Rapid liquidation cascade")
        if snapshot.volatility_1h > 0.1:
            conditions.append("Abnormal short-term volatility")
        
        # Safe denominator for imbalance
        total_depth = snapshot.bid_depth + snapshot.ask_depth
        if total_depth > 0:
            if abs(snapshot.bid_depth - snapshot.ask_depth) / total_depth > 0.8:
                conditions.append("Order-book imbalance")
                
        if abs(snapshot.funding_rate) > 0.005:
            conditions.append("Funding extremes")
            
        detected = len(conditions) > 0
        recommendation = 'REDUCE_EXECUTION' if detected else 'NORMAL'
        if len(conditions) >= 3:
            recommendation = 'DENY_EXECUTION'
            
        return StopHuntAlert(detected=detected, conditions=conditions, recommendation=recommendation)
