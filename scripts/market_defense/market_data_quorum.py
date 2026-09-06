from __future__ import annotations
import enum
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Optional

class DataSource(enum.Enum):
    SOURCE_A = 'SOURCE_A'
    SOURCE_B = 'SOURCE_B'
    SOURCE_C = 'SOURCE_C'

class QuorumVerdict(enum.Enum):
    QUORUM_MET = 'QUORUM_MET'
    DATA_CONFLICT = 'DATA_CONFLICT'
    INSUFFICIENT_SOURCES = 'INSUFFICIENT_SOURCES'
    STALE_DATA = 'STALE_DATA'

@dataclass
class PriceObservation:
    source: str
    instrument: str
    price: float
    timestamp: datetime
    spread: float
    source_healthy: bool

@dataclass
class QuorumResult:
    verdict: QuorumVerdict
    median_price: float
    max_divergence_pct: float
    stale_sources: List[str]
    healthy_sources: List[str]

@dataclass
class LatencyMeasurement:
    signal_ts: datetime
    decision_ts: datetime
    order_intent_ts: datetime
    venue_ack_ts: datetime
    fill_ts: datetime

class MarketDataQuorum:
    MINIMUM_SOURCES = 2
    MAX_PRICE_DIVERGENCE_PCT = 0.5
    MAX_STALENESS_SECONDS = 30

    def evaluate_quorum(self, observations: List[PriceObservation]) -> QuorumResult:
        if not observations:
            return QuorumResult(QuorumVerdict.INSUFFICIENT_SOURCES, 0.0, 0.0, [], [])
            
        now = datetime.now(timezone.utc)
        healthy_obs = []
        stale_sources = []
        healthy_sources = []
        
        for obs in observations:
            staleness = (now - obs.timestamp).total_seconds()
            if staleness > self.MAX_STALENESS_SECONDS:
                stale_sources.append(obs.source)
            elif not obs.source_healthy:
                pass
            else:
                healthy_obs.append(obs)
                healthy_sources.append(obs.source)
                
        if len(healthy_obs) < self.MINIMUM_SOURCES:
            if stale_sources:
                return QuorumResult(QuorumVerdict.STALE_DATA, 0.0, 0.0, stale_sources, healthy_sources)
            return QuorumResult(QuorumVerdict.INSUFFICIENT_SOURCES, 0.0, 0.0, stale_sources, healthy_sources)
            
        prices = [obs.price for obs in healthy_obs]
        prices.sort()
        mid = len(prices) // 2
        median_price = (prices[mid] + prices[~mid]) / 2.0
        
        min_price = min(prices)
        max_price = max(prices)
        max_divergence_pct = ((max_price - min_price) / min_price) * 100.0 if min_price > 0 else 0.0
        
        if max_divergence_pct > self.MAX_PRICE_DIVERGENCE_PCT:
            return QuorumResult(QuorumVerdict.DATA_CONFLICT, median_price, max_divergence_pct, stale_sources, healthy_sources)
            
        return QuorumResult(QuorumVerdict.QUORUM_MET, median_price, max_divergence_pct, stale_sources, healthy_sources)

    def check_execution_feasibility(self, latency: LatencyMeasurement, opportunity_duration_seconds: float) -> bool:
        total_latency = (latency.fill_ts - latency.signal_ts).total_seconds()
        return total_latency < opportunity_duration_seconds

    def calculate_realized_latency(self, latency: LatencyMeasurement) -> Dict[str, float]:
        return {
            'signal_to_decision': (latency.decision_ts - latency.signal_ts).total_seconds(),
            'decision_to_order': (latency.order_intent_ts - latency.decision_ts).total_seconds(),
            'order_to_fill': (latency.fill_ts - latency.order_intent_ts).total_seconds(),
            'total': (latency.fill_ts - latency.signal_ts).total_seconds()
        }
