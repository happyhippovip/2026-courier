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

        if book.is_stale is True:
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

        net = breakdown.net_profit_usd
        if (
            isinstance(net, bool)
            or not isinstance(net, (int, float))
            or not math.isfinite(net)
        ):
            risk_score += 100
            flags.append("NON_FINITE_NET")
            explanation_parts.append("Net profit is not a finite number.")
        elif net < 0:
            risk_score += 100
            flags.append("NEGATIVE_NET")
            explanation_parts.append("Net profit is negative.")

        roi = breakdown.net_roi_pct
        if (
            isinstance(roi, bool)
            or not isinstance(roi, (int, float))
            or not math.isfinite(roi)
        ):
            risk_score += 100
            flags.append("NON_FINITE_ROI")
            explanation_parts.append("ROI is not a finite number.")
        elif roi < 0:
            risk_score += 100
            flags.append("NEGATIVE_ROI")
            explanation_parts.append("ROI is negative.")

        size = breakdown.order_size_usd
        if (
            isinstance(size, bool)
            or not isinstance(size, (int, float))
            or not math.isfinite(size)
        ):
            risk_score += 100
            flags.append("NON_FINITE_SIZE")
            explanation_parts.append("Order size is not a finite number.")
        elif size < 0:
            risk_score += 100
            flags.append("NEGATIVE_SIZE")
            explanation_parts.append("Order size is negative.")

        cost = breakdown.total_costs_usd
        if (
            isinstance(cost, bool)
            or not isinstance(cost, (int, float))
            or not math.isfinite(cost)
        ):
            risk_score += 100
            flags.append("NON_FINITE_COST")
            explanation_parts.append("Total cost is not a finite number.")

        spread_pct = breakdown.gross_spread_pct
        if (
            isinstance(spread_pct, bool)
            or not isinstance(spread_pct, (int, float))
            or not math.isfinite(spread_pct)
        ):
            risk_score += 100
            flags.append("NON_FINITE_SPREAD_PCT")
            explanation_parts.append("Gross spread percent is not a finite number.")
        elif spread_pct < 0:
            risk_score += 100
            flags.append("NEGATIVE_SPREAD_PCT")
            explanation_parts.append("Gross spread percent is negative.")

        transfer = breakdown.transfer_cost_usd
        if (
            isinstance(transfer, bool)
            or not isinstance(transfer, (int, float))
            or not math.isfinite(transfer)
        ):
            risk_score += 100
            flags.append("NON_FINITE_TRANSFER")
            explanation_parts.append("Transfer cost is not a finite number.")

        rebalance = breakdown.rebalance_cost_usd
        if (
            isinstance(rebalance, bool)
            or not isinstance(rebalance, (int, float))
            or not math.isfinite(rebalance)
        ):
            risk_score += 100
            flags.append("NON_FINITE_REBALANCE")
            explanation_parts.append("Rebalance cost is not a finite number.")

        ask = breakdown.best_ask_price
        if (
            isinstance(ask, bool)
            or not isinstance(ask, (int, float))
            or not math.isfinite(ask)
        ):
            risk_score += 100
            flags.append("NON_FINITE_ASK")
            explanation_parts.append("Ask price is not a finite number.")
        elif ask < 0:
            risk_score += 100
            flags.append("NEGATIVE_ASK")
            explanation_parts.append("Ask price is negative.")

        bid = breakdown.best_bid_price
        if (
            isinstance(bid, bool)
            or not isinstance(bid, (int, float))
            or not math.isfinite(bid)
        ):
            risk_score += 100
            flags.append("NON_FINITE_BID")
            explanation_parts.append("Bid price is not a finite number.")
        elif bid < 0:
            risk_score += 100
            flags.append("NEGATIVE_BID")
            explanation_parts.append("Bid price is negative.")

        buy_price = breakdown.effective_buy_price
        if (
            isinstance(buy_price, bool)
            or not isinstance(buy_price, (int, float))
            or not math.isfinite(buy_price)
        ):
            risk_score += 100
            flags.append("NON_FINITE_BUY_PRICE")
            explanation_parts.append("Buy price is not a finite number.")
        elif buy_price < 0:
            risk_score += 100
            flags.append("NEGATIVE_BUY_PRICE")
            explanation_parts.append("Buy price is negative.")

        sell_price = breakdown.effective_sell_price
        if (
            isinstance(sell_price, bool)
            or not isinstance(sell_price, (int, float))
            or not math.isfinite(sell_price)
        ):
            risk_score += 100
            flags.append("NON_FINITE_SELL_PRICE")
            explanation_parts.append("Sell price is not a finite number.")
        elif sell_price < 0:
            risk_score += 100
            flags.append("NEGATIVE_SELL_PRICE")
            explanation_parts.append("Sell price is negative.")

        gross = breakdown.gross_spread_usd
        if (
            isinstance(gross, bool)
            or not isinstance(gross, (int, float))
            or not math.isfinite(gross)
        ):
            risk_score += 100
            flags.append("NON_FINITE_GROSS")
            explanation_parts.append("Gross spread is not a finite number.")
            gross_ok = False
        elif gross < 0:
            risk_score += 100
            flags.append("NEGATIVE_GROSS")
            explanation_parts.append("Gross spread is negative.")
            gross_ok = False
        else:
            gross_ok = True

        # Slippage friction check
        slip = breakdown.slippage_usd
        if (
            isinstance(slip, bool)
            or not isinstance(slip, (int, float))
            or not math.isfinite(slip)
        ):
            risk_score += 100
            flags.append("NON_FINITE_SLIPPAGE")
            explanation_parts.append("Slippage is not a finite number.")
        elif slip < 0:
            risk_score += 100
            flags.append("NEGATIVE_SLIPPAGE")
            explanation_parts.append("Slippage is negative.")
        elif gross_ok and slip > (gross * 0.4):
            risk_score += 25
            flags.append("HIGH_SLIPPAGE_DRAG")
            explanation_parts.append("Orderbook depth slippage consumes over 40% of gross spread.")

        # Fee ratio check
        buy_fee = breakdown.buy_fee_usd
        sell_fee = breakdown.sell_fee_usd
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in (buy_fee, sell_fee)
        ):
            risk_score += 100
            flags.append("NON_FINITE_FEE")
            explanation_parts.append("Fee is not a finite number.")
        else:
            total_fees = buy_fee + sell_fee
            if buy_fee < 0 or sell_fee < 0:
                risk_score += 100
                flags.append("NEGATIVE_FEE")
                explanation_parts.append("Fee is negative.")
            elif gross_ok and total_fees > (gross * 0.7):
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
