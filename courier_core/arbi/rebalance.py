"""Delta-Neutral Rebalancing & Inventory Risk Engine for Binance ↔ Kraken Arbitrage.

Evaluates:
- Venue inventory imbalance (e.g., too much EUR on Binance, too little on Kraken).
- Rebalancing cost threshold vs accumulated arbitrage net profits.
- Soft circuit-breakers preventing one-way capital drain.
- Safety Invariants: REAL_TRADES=0, WALLET_SIGNING=NO, ZERO_ADDITIONAL_COST.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class InventoryStatus:
    venue: str
    quote_balance: float  # EUR or USDT
    base_balance: float   # BTC or ETH
    target_quote_weight: float = 0.5


@dataclass
class RebalanceAssessment:
    is_rebalance_needed: bool
    source_venue: str
    destination_venue: str
    transfer_amount_quote: float
    estimated_network_fee: float
    accumulated_net_profit: float
    rebalance_safe: bool
    status: str
    reason: str


class DeltaNeutralRebalanceEngine:
    """Monitors inventory skew across Binance and Kraken to ensure delta neutrality."""

    def __init__(
        self,
        imbalance_threshold_pct: float = 25.0,
        fixed_transfer_fee_eur: float = 1.50,
        min_profit_to_rebalance_ratio: float = 3.0,
    ):
        settings = (imbalance_threshold_pct, fixed_transfer_fee_eur, min_profit_to_rebalance_ratio)
        if any(isinstance(value, bool) for value in settings):
            raise ValueError("Bool is not a number.")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in settings):
            raise ValueError("rebalance setting is not a number.")
        if fixed_transfer_fee_eur < 0:
            raise ValueError("rebalance setting is out of range.")
        self.imbalance_threshold_pct = imbalance_threshold_pct
        self.fixed_transfer_fee_eur = fixed_transfer_fee_eur
        self.min_profit_to_rebalance_ratio = min_profit_to_rebalance_ratio

    def evaluate_inventory_balance(
        self,
        binance_inv: InventoryStatus,
        kraken_inv: InventoryStatus,
        accumulated_pnl_eur: float,
    ) -> RebalanceAssessment:
        amounts = (
            binance_inv.quote_balance,
            binance_inv.base_balance,
            kraken_inv.quote_balance,
            kraken_inv.base_balance,
            accumulated_pnl_eur,
        )
        if any(isinstance(value, bool) for value in amounts):
            raise ValueError("Bool is not a number.")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in amounts):
            raise ValueError("inventory is not a number.")
        total_quote = binance_inv.quote_balance + kraken_inv.quote_balance
        if total_quote <= 0:
            return RebalanceAssessment(
                is_rebalance_needed=False,
                source_venue="NONE",
                destination_venue="NONE",
                transfer_amount_quote=0.0,
                estimated_network_fee=0.0,
                accumulated_net_profit=accumulated_pnl_eur,
                rebalance_safe=False,
                status="INVENTORY_EMPTY",
                reason="Total virtual inventory is zero",
            )

        binance_pct = (binance_inv.quote_balance / total_quote) * 100.0
        kraken_pct = (kraken_inv.quote_balance / total_quote) * 100.0
        diff_pct = abs(binance_pct - kraken_pct)

        if diff_pct <= self.imbalance_threshold_pct:
            return RebalanceAssessment(
                is_rebalance_needed=False,
                source_venue="BALANCED",
                destination_venue="BALANCED",
                transfer_amount_quote=0.0,
                estimated_network_fee=0.0,
                accumulated_net_profit=accumulated_pnl_eur,
                rebalance_safe=True,
                status="BALANCED",
                reason=f"Skew ({diff_pct:.1f}%) within allowable threshold ({self.imbalance_threshold_pct}%)",
            )

        # Inventory is skewed
        if binance_inv.quote_balance > kraken_inv.quote_balance:
            src = "binance"
            dst = "kraken"
            surplus = (binance_inv.quote_balance - kraken_inv.quote_balance) / 2.0
        else:
            src = "kraken"
            dst = "binance"
            surplus = (kraken_inv.quote_balance - binance_inv.quote_balance) / 2.0

        transfer_amt = round(surplus, 2)
        fee = self.fixed_transfer_fee_eur

        # Cost check: accumulated profits must exceed transfer fee * ratio
        rebalance_safe = accumulated_pnl_eur >= (fee * self.min_profit_to_rebalance_ratio)
        status = "REBALANCE_RECOMMENDED" if rebalance_safe else "REBALANCE_BLOCKED_INSUFFICIENT_PROFIT"
        reason = (
            f"Transfer {transfer_amt:.2f} EUR from {src} to {dst}. "
            f"Accumulated PnL ({accumulated_pnl_eur:.2f} EUR) {'sufficient' if rebalance_safe else 'insufficient'} to cover fee ({fee:.2f} EUR)."
        )

        return RebalanceAssessment(
            is_rebalance_needed=True,
            source_venue=src,
            destination_venue=dst,
            transfer_amount_quote=transfer_amt,
            estimated_network_fee=fee,
            accumulated_net_profit=accumulated_pnl_eur,
            rebalance_safe=rebalance_safe,
            status=status,
            reason=reason,
        )
