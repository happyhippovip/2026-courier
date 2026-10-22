"""Arbitrage Strategies Suite (Cross-Exchange, Triangular, Stress-Testing).

Provides deterministic comparative evaluation of:
A. Cross-Exchange Spot-Arbitrage
B. Triangular Arbitrage (Intra-Exchange)
C. Liquidity & Depth Stress-Testing
D. Historical Spread & Fee Tolerance Analysis
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from courier_core.arbi.models import NormalizedPair, OrderbookSnapshot
from courier_core.arbi.net_profit import NetProfitBreakdown, NetProfitEngine


@dataclass
class TriangularArbiOpportunity:
    exchange: str
    leg1: str  # e.g. "USDT -> BTC"
    leg2: str  # e.g. "BTC -> ETH"
    leg3: str  # e.g. "ETH -> USDT"
    input_capital_usd: float
    output_capital_usd: float
    gross_roi_pct: float
    net_roi_pct: float
    total_fees_usd: float
    status: str
    reason: str


class ArbitrageStrategies:
    """Evaluates various arbitrage strategies deterministically."""

    @classmethod
    def evaluate_triangular_arbitrage(
        cls,
        exchange: str,
        price_a_b: float,  # e.g. BTC/USDT price
        price_b_c: float,  # e.g. ETH/BTC price
        price_c_a: float,  # e.g. ETH/USDT price
        capital_usd: float = 100.0,
        taker_fee_pct: float = 0.10,
    ) -> TriangularArbiOpportunity:
        """Simulates A -> B -> C -> A triangular trade cycle on one venue.
        
        Example: USDT -> BTC -> ETH -> USDT:
        1. Buy BTC with USDT: btc_amount = (capital / price_a_b) * (1 - fee)
        2. Buy ETH with BTC: eth_amount = (btc_amount / price_b_c) * (1 - fee)
        3. Sell ETH for USDT: final_usdt = (eth_amount * price_c_a) * (1 - fee)
        """
        if any(
            isinstance(value, bool)
            for value in (price_a_b, price_b_c, price_c_a, capital_usd, taker_fee_pct)
        ):
            raise ValueError("Bool is not a number.")
        if any(
            not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in (price_a_b, price_b_c, price_c_a, capital_usd, taker_fee_pct)
        ):
            return TriangularArbiOpportunity(
                exchange=exchange,
                leg1="USDT -> BTC",
                leg2="BTC -> ETH",
                leg3="ETH -> USDT",
                input_capital_usd=0.0,
                output_capital_usd=0.0,
                gross_roi_pct=0.0,
                net_roi_pct=0.0,
                total_fees_usd=0.0,
                status="BLOCKED_INVALID_PRICE",
                reason="Invalid prices",
            )
        if taker_fee_pct < 0 or taker_fee_pct > 100:
            return TriangularArbiOpportunity(
                exchange=exchange,
                leg1="USDT -> BTC",
                leg2="BTC -> ETH",
                leg3="ETH -> USDT",
                input_capital_usd=0.0,
                output_capital_usd=0.0,
                gross_roi_pct=0.0,
                net_roi_pct=0.0,
                total_fees_usd=0.0,
                status="BLOCKED_INVALID_PRICE",
                reason="Invalid fee",
            )
        if price_a_b <= 0 or price_b_c <= 0 or price_c_a <= 0 or capital_usd <= 0:
            return TriangularArbiOpportunity(
                exchange=exchange,
                leg1="USDT -> BTC",
                leg2="BTC -> ETH",
                leg3="ETH -> USDT",
                input_capital_usd=0.0,
                output_capital_usd=0.0,
                gross_roi_pct=0.0,
                net_roi_pct=0.0,
                total_fees_usd=0.0,
                status="BLOCKED_INVALID_PRICE",
                reason="Invalid prices",
            )
        fee_mult = 1.0 - (taker_fee_pct / 100.0)

        # Step 1: Buy B with A
        b_amount = (capital_usd / price_a_b) * fee_mult
        fee_step1 = capital_usd * (taker_fee_pct / 100.0)

        # Step 2: Buy C with B
        c_amount = (b_amount / price_b_c) * fee_mult
        fee_step2 = (b_amount * price_a_b) * (taker_fee_pct / 100.0)

        # Step 3: Sell C for A
        final_usd = (c_amount * price_c_a) * fee_mult
        fee_step3 = (c_amount * price_c_a) * (taker_fee_pct / 100.0)

        total_fees = fee_step1 + fee_step2 + fee_step3
        net_profit = final_usd - capital_usd
        net_roi = (net_profit / capital_usd) * 100.0

        # Theoretical gross without fees
        gross_final = (capital_usd / price_a_b / price_b_c) * price_c_a
        gross_roi = ((gross_final - capital_usd) / capital_usd) * 100.0

        if net_profit > 0:
            status = "ELIGIBLE"
            reason = f"Viable triangular opportunity (+{net_profit:.2f} USD)"
        else:
            status = "BLOCKED_NEGATIVE_NET"
            reason = f"3-leg fees ({total_fees:.2f} USD) exceed gross cycle (+{gross_final - capital_usd:.2f} USD)"

        return TriangularArbiOpportunity(
            exchange=exchange,
            leg1=f"USDT -> BTC (@{price_a_b:.2f})",
            leg2=f"BTC -> ETH (@{price_b_c:.6f})",
            leg3=f"ETH -> USDT (@{price_c_a:.2f})",
            input_capital_usd=capital_usd,
            output_capital_usd=round(final_usd, 4),
            gross_roi_pct=round(gross_roi, 4),
            net_roi_pct=round(net_roi, 4),
            total_fees_usd=round(total_fees, 4),
            status=status,
            reason=reason,
        )

    @classmethod
    def stress_test_slippage(
        cls,
        pair: NormalizedPair,
        buy_book: OrderbookSnapshot,
        sell_book: OrderbookSnapshot,
        test_sizes_usd: list[float],
    ) -> list[NetProfitBreakdown]:
        """Tests opportunity degradation across increasing order sizes."""
        results = []
        for size in test_sizes_usd:
            bd = NetProfitEngine.evaluate_opportunity(pair, buy_book, sell_book, order_size_usd=size)
            results.append(bd)
        return results
