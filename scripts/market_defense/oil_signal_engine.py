from __future__ import annotations
import enum
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

class OilInstrument(enum.Enum):
    WTI = 'WTI'
    BRENT = 'BRENT'

class OilLivePolicy(enum.Enum):
    DENY = 'DENY'
    ALLOW = 'ALLOW'

@dataclass
class OilSnapshot:
    timestamp: datetime
    wti_price: float
    brent_price: float
    front_month_price: float
    next_month_price: float
    contango_backwardation: float
    inventory_surprise_pct: float
    refinery_utilization_pct: float
    gasoline_stocks_delta: float
    distillate_stocks_delta: float
    us_production_mbpd: float
    imports_exports_delta: float
    opec_supply_signal: float
    shipping_disruption_active: bool
    refinery_outage_active: bool
    pipeline_outage_active: bool
    geopolitical_shock_active: bool
    natgas_price: float
    usd_index: float

@dataclass
class OilSignalResult:
    verdict: str
    bullish_score: float
    bearish_score: float
    dominant_signals: List[str]
    risk_factors: List[str]

@dataclass
class OilPreLiveProof:
    exact_instrument: bool
    maximum_possible_loss: bool
    no_physical_delivery: bool
    no_unbounded_margin: bool
    expiry_guard: bool
    auto_close_before_dangerous_window: bool
    roll_policy: bool
    fee_model: bool
    slippage_model: bool

class OilSignalEngine:
    OIL_LIVE_POLICY = OilLivePolicy.DENY
    OIL_PAPER_POLICY = OilLivePolicy.ALLOW

    def evaluate_oil(self, snapshot: OilSnapshot) -> OilSignalResult:
        return OilSignalResult("NO_TRADE", 0.0, 0.0, [], [])

    def check_pre_live_requirements(self, proof: OilPreLiveProof) -> bool:
        if not proof.exact_instrument: return False
        if not proof.maximum_possible_loss: return False
        if not proof.no_physical_delivery: return False
        if not proof.no_unbounded_margin: return False
        if not proof.expiry_guard: return False
        if not proof.auto_close_before_dangerous_window: return False
        if not proof.roll_policy: return False
        if not proof.fee_model: return False
        if not proof.slippage_model: return False
        return True

    def is_live_authorized(self) -> bool:
        return False
