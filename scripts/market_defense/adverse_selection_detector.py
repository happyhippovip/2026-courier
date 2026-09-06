from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List

@dataclass
class FillAnalysis:
    trade_id: str
    price_at_decision: float
    price_at_submit: float
    price_at_fill: float
    price_1s_after: float
    price_5s_after: float
    price_30s_after: float
    price_60s_after: float

@dataclass
class SelectionMetrics:
    implementation_shortfall: float
    slippage: float
    post_fill_adverse_1s: float
    post_fill_adverse_5s: float
    post_fill_adverse_30s: float
    post_fill_adverse_60s: float
    adversely_selected: bool

@dataclass
class PatternResult:
    pattern_detected: bool
    adverse_fill_rate: float
    avg_slippage: float
    avg_adverse_1s: float
    recommendation: str

class AdverseSelectionDetector:
    def calculate_metrics(self, fill: FillAnalysis, direction: str) -> SelectionMetrics:
        if direction == 'LONG':
            slippage = fill.price_at_fill - fill.price_at_submit
            shortfall = fill.price_at_fill - fill.price_at_decision
            adv_1s = fill.price_at_fill - fill.price_1s_after
            adv_5s = fill.price_at_fill - fill.price_5s_after
            adv_30s = fill.price_at_fill - fill.price_30s_after
            adv_60s = fill.price_at_fill - fill.price_60s_after
        else:
            slippage = fill.price_at_submit - fill.price_at_fill
            shortfall = fill.price_at_decision - fill.price_at_fill
            adv_1s = fill.price_1s_after - fill.price_at_fill
            adv_5s = fill.price_5s_after - fill.price_at_fill
            adv_30s = fill.price_30s_after - fill.price_at_fill
            adv_60s = fill.price_60s_after - fill.price_at_fill
            
        adverse = adv_60s > 0

        return SelectionMetrics(
            implementation_shortfall=shortfall,
            slippage=slippage,
            post_fill_adverse_1s=adv_1s,
            post_fill_adverse_5s=adv_5s,
            post_fill_adverse_30s=adv_30s,
            post_fill_adverse_60s=adv_60s,
            adversely_selected=adverse
        )

    def detect_pattern(self, history: List[SelectionMetrics]) -> PatternResult:
        if not history:
            return PatternResult(False, 0.0, 0.0, 0.0, 'NORMAL')
            
        adverse_count = sum(1 for m in history if m.adversely_selected)
        rate = adverse_count / len(history)
        avg_slip = sum(m.slippage for m in history) / len(history)
        avg_adv1 = sum(m.post_fill_adverse_1s for m in history) / len(history)
        
        detected = rate > 0.60
        rec = 'DISABLE_STRATEGY' if rate > 0.8 else ('INVESTIGATE' if detected else 'NORMAL')
        
        return PatternResult(detected, rate, avg_slip, avg_adv1, rec)

class ExecutionRandomizer:
    def randomize_poll_interval(self, base_seconds: float, jitter_pct: float = 0.1) -> float:
        jitter = base_seconds * jitter_pct
        return base_seconds + random.uniform(-jitter, jitter)

    def is_safe_to_randomize(self, parameter: str) -> bool:
        unsafe = {'amount', 'stop', 'destination', 'instrument', 'capital_limit'}
        return parameter not in unsafe
