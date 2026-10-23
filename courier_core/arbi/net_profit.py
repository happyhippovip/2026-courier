"""Realistic Net Profit Calculation Engine.

Calculates:
- Gross spread
- Buy & Sell maker/taker fees
- Orderbook slippage from depth
- Transfer & rebalancing costs
- Net profit & ROI
- Opportunity status (ELIGIBLE vs BLOCKED)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from courier_core.arbi.models import (
    DEFAULT_FEE_SCHEDULES,
    ExchangeFeeSchedule,
    NormalizedPair,
    OrderbookSnapshot,
)


@dataclass
class NetProfitBreakdown:
    pair: NormalizedPair
    buy_exchange: str
    sell_exchange: str
    order_size_usd: float

    # Pricing
    best_ask_price: float
    best_bid_price: float
    effective_buy_price: float
    effective_sell_price: float

    # Raw metrics
    gross_spread_pct: float
    gross_spread_usd: float

    # Fees and frictions
    buy_fee_usd: float
    sell_fee_usd: float
    slippage_usd: float
    transfer_cost_usd: float
    rebalance_cost_usd: float
    total_costs_usd: float

    # Final result
    net_profit_usd: float
    net_roi_pct: float
    status: str  # "ELIGIBLE", "BLOCKED_FEE_EXCEEDS_SPREAD", "BLOCKED_STALE", "BLOCKED_INSUFFICIENT_DEPTH"
    reason: str


def _reject_bool_fee(sched: ExchangeFeeSchedule) -> None:
    if any(
        isinstance(value, bool)
        for value in (sched.maker_fee_pct, sched.taker_fee_pct, sched.withdrawal_fee_usd)
    ):
        raise ValueError("Bool is not a number.")


def _reject_bool_book(book: Optional[OrderbookSnapshot]) -> None:
    if book is None:
        return
    if isinstance(book.latency_ms, bool):
        raise ValueError("Bool is not a number.")
    for level in (*book.bids, *book.asks):
        if isinstance(level.price, bool) or isinstance(level.amount, bool):
            raise ValueError("Bool is not a number.")


class NetProfitEngine:
    """Calculates realistic net yield after fees, depth slippage, and frictions."""

    @staticmethod
    def calculate_effective_price_and_slippage(
        orders: list,
        target_usd: float,
        is_buy: bool,
    ) -> tuple[float, float, bool]:
        """Walks the orderbook to compute weighted average execution price and slippage.
        
        Returns (effective_price, slippage_usd, has_sufficient_depth).
        """
        if isinstance(target_usd, bool):
            raise ValueError("Bool is not a number.")
        if not orders:
            return 0.0, 0.0, False

        best_price = orders[0].price
        remaining_usd = target_usd
        total_qty = 0.0
        total_spent = 0.0

        for level in orders:
            if isinstance(level.price, bool) or isinstance(level.amount, bool):
                raise ValueError("Bool is not a number.")
            level_usd = level.price * level.amount
            if remaining_usd <= level_usd:
                qty_fill = remaining_usd / level.price
                total_qty += qty_fill
                total_spent += remaining_usd
                remaining_usd = 0.0
                break
            else:
                total_qty += level.amount
                total_spent += level_usd
                remaining_usd -= level_usd

        if remaining_usd > 0.001 or total_qty <= 0:
            # Insufficient depth to absorb order size
            return best_price, 0.0, False

        effective_price = total_spent / total_qty
        if is_buy:
            # For buy, higher effective price means positive slippage cost
            slippage_cost = max(0.0, (effective_price - best_price) * total_qty)
        else:
            # For sell, lower effective price means slippage cost
            slippage_cost = max(0.0, (best_price - effective_price) * total_qty)

        return effective_price, slippage_cost, True

    @classmethod
    def evaluate_opportunity(
        cls,
        pair: NormalizedPair,
        buy_book: Optional[OrderbookSnapshot],
        sell_book: Optional[OrderbookSnapshot],
        order_size_usd: float = 100.0,
        buy_fee_sched: Optional[ExchangeFeeSchedule] = None,
        sell_fee_sched: Optional[ExchangeFeeSchedule] = None,
        include_transfer: bool = False,
    ) -> NetProfitBreakdown:
        if isinstance(order_size_usd, bool):
            raise ValueError("Bool is not a number.")
        _reject_bool_book(buy_book)
        _reject_bool_book(sell_book)
        if not buy_book or not sell_book:
            return cls._blocked_breakdown(pair, "UNKNOWN", "UNKNOWN", order_size_usd, "BLOCKED_DATA_UNAVAILABLE", "One or both books missing")

        if buy_book.is_stale or sell_book.is_stale:
            return cls._blocked_breakdown(pair, buy_book.exchange, sell_book.exchange, order_size_usd, "BLOCKED_STALE", "Data older than max age threshold")

        best_ask = buy_book.best_ask
        best_bid = sell_book.best_bid
        if not best_ask or not best_bid or best_ask <= 0 or best_bid <= 0:
            return cls._blocked_breakdown(pair, buy_book.exchange, sell_book.exchange, order_size_usd, "BLOCKED_INVALID_PRICE", "Invalid quotes")

        # Orderbook depth slippage analysis
        eff_buy, buy_slip, buy_ok = cls.calculate_effective_price_and_slippage(buy_book.asks, order_size_usd, is_buy=True)
        eff_sell, sell_slip, sell_ok = cls.calculate_effective_price_and_slippage(sell_book.bids, order_size_usd, is_buy=False)

        if not buy_ok or not sell_ok:
            return cls._blocked_breakdown(
                pair, buy_book.exchange, sell_book.exchange, order_size_usd,
                "BLOCKED_INSUFFICIENT_DEPTH", "Orderbook depth cannot fill requested size"
            )

        # Fees
        b_fees = buy_fee_sched or DEFAULT_FEE_SCHEDULES.get(buy_book.exchange, ExchangeFeeSchedule(buy_book.exchange, 0.1, 0.1))
        s_fees = sell_fee_sched or DEFAULT_FEE_SCHEDULES.get(sell_book.exchange, ExchangeFeeSchedule(sell_book.exchange, 0.1, 0.1))
        _reject_bool_fee(b_fees)
        _reject_bool_fee(s_fees)

        buy_fee_usd = order_size_usd * (b_fees.taker_fee_pct / 100.0)
        sell_fee_usd = order_size_usd * (s_fees.taker_fee_pct / 100.0)
        slippage_usd = buy_slip + sell_slip
        transfer_cost_usd = (b_fees.withdrawal_fee_usd if include_transfer else 0.0)
        rebalance_cost_usd = 0.0  # Assumes pre-funded capital on both venues in paper mode

        # Gross & Net
        gross_spread_pct = ((best_bid - best_ask) / best_ask) * 100.0
        gross_spread_usd = order_size_usd * (gross_spread_pct / 100.0)

        total_costs = buy_fee_usd + sell_fee_usd + slippage_usd + transfer_cost_usd + rebalance_cost_usd
        net_profit_usd = gross_spread_usd - total_costs
        net_roi_pct = (net_profit_usd / order_size_usd) * 100.0

        if net_profit_usd <= 0:
            status = "BLOCKED_NEGATIVE_NET"
            reason = f"Costs ({total_costs:.2f} USD) exceed gross spread ({gross_spread_usd:.2f} USD)"
        else:
            status = "ELIGIBLE"
            reason = f"Viable net profit (+{net_profit_usd:.2f} USD, {net_roi_pct:.2f}% ROI)"

        return NetProfitBreakdown(
            pair=pair,
            buy_exchange=buy_book.exchange,
            sell_exchange=sell_book.exchange,
            order_size_usd=order_size_usd,
            best_ask_price=best_ask,
            best_bid_price=best_bid,
            effective_buy_price=round(eff_buy, 4),
            effective_sell_price=round(eff_sell, 4),
            gross_spread_pct=round(gross_spread_pct, 4),
            gross_spread_usd=round(gross_spread_usd, 4),
            buy_fee_usd=round(buy_fee_usd, 4),
            sell_fee_usd=round(sell_fee_usd, 4),
            slippage_usd=round(slippage_usd, 4),
            transfer_cost_usd=round(transfer_cost_usd, 4),
            rebalance_cost_usd=round(rebalance_cost_usd, 4),
            total_costs_usd=round(total_costs, 4),
            net_profit_usd=round(net_profit_usd, 4),
            net_roi_pct=round(net_roi_pct, 4),
            status=status,
            reason=reason,
        )

    @staticmethod
    def _blocked_breakdown(pair: NormalizedPair, buy_ex: str, sell_ex: str, size: float, status: str, reason: str) -> NetProfitBreakdown:
        return NetProfitBreakdown(
            pair=pair,
            buy_exchange=buy_ex,
            sell_exchange=sell_ex,
            order_size_usd=size,
            best_ask_price=0.0,
            best_bid_price=0.0,
            effective_buy_price=0.0,
            effective_sell_price=0.0,
            gross_spread_pct=0.0,
            gross_spread_usd=0.0,
            buy_fee_usd=0.0,
            sell_fee_usd=0.0,
            slippage_usd=0.0,
            transfer_cost_usd=0.0,
            rebalance_cost_usd=0.0,
            total_costs_usd=0.0,
            net_profit_usd=0.0,
            net_roi_pct=0.0,
            status=status,
            reason=reason,
        )
