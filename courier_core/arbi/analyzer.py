"""Deterministic AI / Statistical Quality Assessment Module for Arbitrage.

Evaluates:
- Opportunity risk scoring & prioritization
- Bad market data detection (zero depths, negative spreads, inverted orderbooks)
- Deterministic heuristic explanations for why an opportunity is blocked
- Absolute rule: Zero external API calls, zero cost, fully reproducible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from courier_core.arbi.models import OrderbookSnapshot
from courier_core.arbi.net_profit import NetProfitBreakdown


@dataclass
class QualityAssessment:
    opportunity_id: str
    risk_score: int  # 0 to 100 (lower is safer)
    confidence_tier: str  # "HIGH", "MEDIUM", "LOW", "REJECTED"
    data_quality_flags: list[str]
    heuristic_recommendation: str
    explanation: str


class StatisticalQualityAnalyzer:
    """Deterministic analyzer for arbitrage opportunity hygiene and ranking."""

    @classmethod
    def audit_orderbook_integrity(cls, book: Optional[OrderbookSnapshot]) -> list[str]:
        flags: list[str] = []
        if not book:
            flags.append("ORDERBOOK_MISSING")
            return flags

        if not book.bids:
            flags.append("NO_BIDS_AVAILABLE")
        if not book.asks:
            flags.append("NO_ASKS_AVAILABLE")

        bid = book.best_bid
        ask = book.best_ask
        if bid and ask:
            if (
                not isinstance(bid, (int, float))
                or not isinstance(ask, (int, float))
                or not math.isfinite(bid)
                or not math.isfinite(ask)
            ):
                flags.append("NON_FINITE_PRICE")
            else:
                if bid >= ask:
                    flags.append("CROSSED_INTERNAL_ORDERBOOK")
                if bid <= 0 or ask <= 0:
                    flags.append("NON_POSITIVE_PRICE")

        if book.is_stale:
            flags.append("STALE_DATA_TIMESTAMP")

        latency = book.latency_ms
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or not math.isfinite(latency)
        ):
            flags.append("NON_FINITE_LATENCY")
        elif latency > 1500.0:
            flags.append("HIGH_NETWORK_LATENCY")

        return flags

    @classmethod
    def evaluate_and_score(
        cls,
        breakdown: NetProfitBreakdown,
        buy_book: Optional[OrderbookSnapshot] = None,
        sell_book: Optional[OrderbookSnapshot] = None,
    ) -> QualityAssessment:
        opp_id = f"arbi-{breakdown.pair.base}-{breakdown.pair.quote}-{breakdown.buy_exchange}-to-{breakdown.sell_exchange}"
        flags: list[str] = []

        # Audit book hygiene
        flags.extend(cls.audit_orderbook_integrity(buy_book))
        flags.extend(cls.audit_orderbook_integrity(sell_book))

        risk_score = 0
        explanation_parts = []

        # Check status
        if breakdown.status != "ELIGIBLE":
            risk_score += 60
            explanation_parts.append(f"Status not eligible: {breakdown.status} ({breakdown.reason})")

        # Slippage friction check
        if breakdown.slippage_usd > (breakdown.gross_spread_usd * 0.4):
            risk_score += 25
            flags.append("HIGH_SLIPPAGE_DRAG")
            explanation_parts.append("Orderbook depth slippage consumes over 40% of gross spread.")

        # Fee ratio check
        total_fees = breakdown.buy_fee_usd + breakdown.sell_fee_usd
        if total_fees > (breakdown.gross_spread_usd * 0.7):
            risk_score += 20
            flags.append("HIGH_FEE_BURDEN")
            explanation_parts.append("Exchange fees absorb over 70% of gross opportunity.")

        # Data health flags penalty
        if flags:
            risk_score += len(flags) * 15

        risk_score = min(100, max(0, risk_score))

        if risk_score <= 25 and breakdown.status == "ELIGIBLE":
            tier = "HIGH"
            rec = "EXECUTE_IN_PAPER_MODE"
            explanation = "Opportunity demonstrates clean book hygiene, positive net margin after fees, and minimal depth slippage."
        elif risk_score <= 55 and breakdown.status == "ELIGIBLE":
            tier = "MEDIUM"
            rec = "OBSERVE_OR_REDUCE_SIZE"
            explanation = "Net positive but elevated fee or slippage friction. " + " ".join(explanation_parts)
        elif risk_score <= 75:
            tier = "LOW"
            rec = "STANDBY"
            explanation = "Marginal or vulnerable spread. " + " ".join(explanation_parts)
        else:
            tier = "REJECTED"
            rec = "DISCARD"
            explanation = "Critical rejection: " + " ".join(explanation_parts)

        return QualityAssessment(
            opportunity_id=opp_id,
            risk_score=risk_score,
            confidence_tier=tier,
            data_quality_flags=list(set(flags)),
            heuristic_recommendation=rec,
            explanation=explanation,
        )
