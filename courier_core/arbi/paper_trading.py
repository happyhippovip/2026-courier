"""Paper Trading Engine with Virtual Balances & Latency / Partial Fill Simulation.

Supports:
- Virtual capital configs: 52 USD, 100 USD, 500 USD, 1,000 USD
- Per-exchange virtual balance tracking (USDT, base assets)
- Partial fill simulation & second-leg execution risk
- Real-time performance tracking (PnL, win rate, max drawdown)
- Absolute invariant: REAL_TRADES=0, REAL_FUNDS_TOUCHED=NO.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from courier_core.arbi.models import NormalizedPair
from courier_core.arbi.net_profit import NetProfitBreakdown


@dataclass
class SimulatedTradeRecord:
    trade_id: str
    timestamp_utc: str
    pair: str
    buy_exchange: str
    sell_exchange: str
    order_size_usd: float
    gross_spread_usd: float
    fees_usd: float
    slippage_usd: float
    net_pnl_usd: float
    roi_pct: float
    execution_status: str  # "FULL_SUCCESS", "PARTIAL_FILL", "SECOND_LEG_FAILED"
    simulated_latency_ms: float


class PaperTradingEngine:
    """Simulates multi-exchange arbitrage execution with virtual bankrolls."""

    def __init__(self, initial_capital_usd: float = 100.0, simulated_venues: Optional[list[str]] = None):
        if isinstance(initial_capital_usd, bool):
            raise ValueError("Bool is not a number.")
        if not isinstance(initial_capital_usd, (int, float)) or not math.isfinite(initial_capital_usd):
            raise ValueError("virtual capital is not a number.")
        if initial_capital_usd < 0:
            raise ValueError("virtual capital is out of range.")
        self.initial_capital_usd = initial_capital_usd
        self.venues = simulated_venues or ["binance", "bybit", "okx"]
        
        # Distribute virtual quote currency equally across simulated venues
        capital_per_venue = initial_capital_usd / len(self.venues)
        self.virtual_balances: dict[str, dict[str, float]] = {
            v: {"USDT": capital_per_venue, "BASE": 0.0} for v in self.venues
        }
        self.trade_history: list[SimulatedTradeRecord] = []
        self._trade_counter = 0

    @property
    def total_portfolio_usd(self) -> float:
        # Sum of USDT across all venues + net PnL realized
        base_usdt = sum(b.get("USDT", 0.0) for b in self.virtual_balances.values())
        return base_usdt

    @property
    def total_realized_pnl_usd(self) -> float:
        return sum(t.net_pnl_usd for t in self.trade_history)

    @property
    def win_rate_pct(self) -> float:
        if not self.trade_history:
            return 0.0
        wins = sum(1 for t in self.trade_history if t.net_pnl_usd > 0)
        return (wins / len(self.trade_history)) * 100.0

    @property
    def max_drawdown_usd(self) -> float:
        peak = self.initial_capital_usd
        running = self.initial_capital_usd
        max_dd = 0.0

        for t in self.trade_history:
            running += t.net_pnl_usd
            if running > peak:
                peak = running
            dd = peak - running
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 4)

    def execute_paper_arbitrage(
        self,
        breakdown: NetProfitBreakdown,
        simulated_latency_ms: float = 45.0,
        second_leg_fail_rate: float = 0.0,
        partial_fill_pct: float = 100.0,
    ) -> SimulatedTradeRecord:
        """Simulates atomic execution across buy and sell venues."""
        if (
            isinstance(simulated_latency_ms, bool)
            or isinstance(second_leg_fail_rate, bool)
            or isinstance(partial_fill_pct, bool)
            or isinstance(breakdown.order_size_usd, bool)
            or isinstance(breakdown.slippage_usd, bool)
            or isinstance(breakdown.buy_fee_usd, bool)
            or isinstance(breakdown.sell_fee_usd, bool)
            or isinstance(breakdown.gross_spread_usd, bool)
        ):
            raise ValueError("Bool is not a number.")
        size = breakdown.order_size_usd
        if not isinstance(size, (int, float)) or not math.isfinite(size):
            raise ValueError("order size is not a number.")
        if size <= 0:
            raise ValueError("order size is out of range.")
        slip = breakdown.slippage_usd
        if not isinstance(slip, (int, float)) or not math.isfinite(slip):
            raise ValueError("slippage is not a number.")
        if slip < 0:
            raise ValueError("slippage is out of range.")
        if any(
            not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in (breakdown.buy_fee_usd, breakdown.sell_fee_usd)
        ):
            raise ValueError("fee is not a number.")
        if breakdown.buy_fee_usd < 0 or breakdown.sell_fee_usd < 0:
            raise ValueError("fee is out of range.")
        gross = breakdown.gross_spread_usd
        if not isinstance(gross, (int, float)) or not math.isfinite(gross):
            raise ValueError("gross spread is not a number.")
        if gross <= 0:
            raise ValueError("gross spread is out of range.")
        if not isinstance(partial_fill_pct, (int, float)) or not math.isfinite(partial_fill_pct):
            raise ValueError("fill percent is not a number.")
        if not isinstance(second_leg_fail_rate, (int, float)) or not math.isfinite(second_leg_fail_rate):
            raise ValueError("fail rate is not a number.")
        if not 0.0 <= second_leg_fail_rate <= 1.0:
            raise ValueError("fail rate is out of range.")
        if not isinstance(simulated_latency_ms, (int, float)) or not math.isfinite(simulated_latency_ms):
            raise ValueError("latency is not a number.")
        if simulated_latency_ms < 0:
            raise ValueError("latency is out of range.")
        self._trade_counter += 1
        t_id = f"sim-trade-{self._trade_counter:04d}"

        buy_ex = breakdown.buy_exchange
        sell_ex = breakdown.sell_exchange

        # Verify virtual balance on buy exchange
        current_usdt = self.virtual_balances.get(buy_ex, {}).get("USDT", 0.0)
        fill_fraction = min(1.0, max(0.1, partial_fill_pct / 100.0))
        effective_size = breakdown.order_size_usd * fill_fraction

        if current_usdt < effective_size:
            # Scaled down to available balance
            effective_size = current_usdt

        if effective_size <= 0:
            rec = SimulatedTradeRecord(
                trade_id=t_id,
                timestamp_utc=breakdown.reason,
                pair=breakdown.pair.canonical,
                buy_exchange=buy_ex,
                sell_exchange=sell_ex,
                order_size_usd=0.0,
                gross_spread_usd=0.0,
                fees_usd=0.0,
                slippage_usd=0.0,
                net_pnl_usd=0.0,
                roi_pct=0.0,
                execution_status="REJECTED_INSUFFICIENT_VIRTUAL_BALANCE",
                simulated_latency_ms=simulated_latency_ms,
            )
            self.trade_history.append(rec)
            return rec

        # Scaled economics
        scale = effective_size / breakdown.order_size_usd if breakdown.order_size_usd > 0 else 1.0
        gross_usd = breakdown.gross_spread_usd * scale
        fees_usd = (breakdown.buy_fee_usd + breakdown.sell_fee_usd) * scale
        slip_usd = breakdown.slippage_usd * scale

        # Execution risk check (second leg failure or adverse move due to latency)
        if second_leg_fail_rate > 0.0 and (self._trade_counter % int(1.0 / second_leg_fail_rate) == 0):
            # Second leg failed! Position stuck on buy venue, unhedged liquidation penalty (-1.5%)
            liquidation_penalty_usd = effective_size * 0.015
            net_pnl = -(breakdown.buy_fee_usd * scale + liquidation_penalty_usd)
            status = "SECOND_LEG_FAILED"
        else:
            net_pnl = gross_usd - (fees_usd + slip_usd)
            status = "FULL_SUCCESS" if fill_fraction >= 0.999 else "PARTIAL_FILL"

        # Apply to virtual balances
        self.virtual_balances[buy_ex]["USDT"] -= effective_size
        self.virtual_balances[sell_ex]["USDT"] += (effective_size + net_pnl)

        roi = (net_pnl / effective_size) * 100.0 if effective_size > 0 else 0.0

        record = SimulatedTradeRecord(
            trade_id=t_id,
            timestamp_utc="SIMULATED_TICK",
            pair=breakdown.pair.canonical,
            buy_exchange=buy_ex,
            sell_exchange=sell_ex,
            order_size_usd=round(effective_size, 2),
            gross_spread_usd=round(gross_usd, 4),
            fees_usd=round(fees_usd, 4),
            slippage_usd=round(slip_usd, 4),
            net_pnl_usd=round(net_pnl, 4),
            roi_pct=round(roi, 4),
            execution_status=status,
            simulated_latency_ms=simulated_latency_ms,
        )
        self.trade_history.append(record)
        return record
