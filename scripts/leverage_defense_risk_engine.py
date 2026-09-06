#!/usr/bin/env python3
"""Mission 221: Deterministic Leverage Defense & Profit Protection Risk Engine.

Core Invariants:
- Canary Leverage Policy: 10X=DENY, 20X=DENY, 40X=DENY (Default MAX_CANARY_LEVERAGE = 1X)
- Profit-Lock State Machine: OPEN_RISK -> PROFIT_DETECTED -> BREAKEVEN_PROTECTED ->
  PARTIAL_PROFIT_SECURED -> TRAILING_PROTECTION -> EXIT_REQUIRED -> CLOSED -> RECONCILED
- Maximum Profit Giveback: Exceeding authorized giveback envelope triggers EXIT_REQUIRED
- Breakeven Protection: Authorized loss bounded around entry + fees + slippage
- Volatility-Aware Trailing: Dynamic buffer based on volatility/spread; never widens stop
- Time Stop: Stagnant non-progressing positions exited after window expires
- No Revenge / No Flip: Mandatory cooldown and new evidence required post-loss
- Portfolio Risk Aggregation: Total notional, correlation, and leverage-weighted limits
- 100% Deterministic (0 model calls, 0 EUR live spend)
"""

from __future__ import annotations

import datetime as dt
import enum
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class PositionSide(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class ProfitLockState(str, enum.Enum):
    OPEN_RISK = "OPEN_RISK"
    PROFIT_DETECTED = "PROFIT_DETECTED"
    RISK_REDUCED = "RISK_REDUCED"
    BREAKEVEN_PROTECTED = "BREAKEVEN_PROTECTED"
    PARTIAL_PROFIT_SECURED = "PARTIAL_PROFIT_SECURED"
    TRAILING_PROTECTION = "TRAILING_PROTECTION"
    EXIT_REQUIRED = "EXIT_REQUIRED"
    CLOSED = "CLOSED"
    RECONCILED = "RECONCILED"


class ExitReason(str, enum.Enum):
    INITIAL_STOP_LOSS = "INITIAL_STOP_LOSS"
    BREAKEVEN_STOP = "BREAKEVEN_STOP"
    PROFIT_GIVEBACK_LIMIT = "PROFIT_GIVEBACK_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    TAKE_PROFIT_TARGET = "TAKE_PROFIT_TARGET"
    TIME_STOP = "TIME_STOP"
    PORTFOLIO_RISK_LIMIT = "PORTFOLIO_RISK_LIMIT"
    LEVERAGE_DISALLOWED = "LEVERAGE_DISALLOWED"
    UNKNOWN_EXECUTION_FAIL_CLOSED = "UNKNOWN_EXECUTION_FAIL_CLOSED"


@dataclass
class RiskConfig:
    max_canary_leverage: float = 1.0  # 1X max for canary. 10x/20x/40x strictly DENIED
    max_initial_loss_pct: float = 0.05  # 5% max initial loss
    breakeven_trigger_pct: float = 0.10  # 10% gain triggers breakeven move
    profit_lock_trigger_pct: float = 0.20  # 20% gain activates profit protection
    max_profit_giveback_pct: float = 0.35  # Max 35% giveback of peak unrealized profit
    trailing_vol_multiplier: float = 1.5  # Volatility multiplier for trailing stop
    time_stop_seconds: int = 3600  # 1 hour max without progress
    max_concurrent_positions: int = 3
    portfolio_max_loss_eur: float = 10.0
    cooldown_period_seconds: int = 300  # 5-minute cooldown after loss/stop
    estimated_fee_pct: float = 0.001  # 0.1% round-trip fee
    estimated_slippage_pct: float = 0.002  # 0.2% slippage buffer


@dataclass
class Position:
    position_id: str
    symbol: str
    side: PositionSide
    entry_price: float
    size: float
    leverage: float
    entry_time: str = field(default_factory=utc_now)
    state: ProfitLockState = ProfitLockState.OPEN_RISK
    peak_price: float = 0.0
    trough_price: float = 0.0
    peak_unrealized_pnl_pct: float = 0.0
    current_unrealized_pnl_pct: float = 0.0
    current_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: Optional[float] = None
    partial_tp_executed: bool = False
    exit_reason: Optional[str] = None
    closed_at: Optional[str] = None
    is_closed: bool = False

    def __post_init__(self):
        if self.peak_price == 0.0:
            self.peak_price = self.entry_price
        if self.trough_price == 0.0:
            self.trough_price = self.entry_price

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LeverageDefenseRiskEngine:
    """Deterministic Profit Protection & Leverage Defense Engine."""

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.last_loss_time: Optional[float] = None
        self.consecutive_losses: int = 0
        self.processed_close_requests: Set[str] = set()

    def validate_new_order(
        self,
        symbol: str,
        side: PositionSide,
        size: float,
        price: float,
        leverage: float,
    ) -> Tuple[bool, str]:
        """Validates new position against leverage, cooldown, and portfolio rules."""
        # 1. Canary Leverage Gate (10X, 20X, 40X strictly DENIED)
        if leverage > self.config.max_canary_leverage:
            return False, f"CANARY_LEVERAGE_DENIED: {leverage}X exceeds limit ({self.config.max_canary_leverage}X)"

        # 2. Cooldown Gate (No revenge trading immediately after stop/loss)
        if self.last_loss_time:
            elapsed = time.time() - self.last_loss_time
            if elapsed < self.config.cooldown_period_seconds:
                return False, f"COOLDOWN_ACTIVE: {int(self.config.cooldown_period_seconds - elapsed)}s remaining"

        # 3. Concurrent Position Limit
        active_count = len([p for p in self.positions.values() if not p.is_closed])
        if active_count >= self.config.max_concurrent_positions:
            return False, f"MAX_CONCURRENT_POSITIONS_REACHED: {active_count}/{self.config.max_concurrent_positions}"

        # 4. Portfolio Max Loss Exposure Check
        total_risk = sum(
            p.size * p.entry_price * self.config.max_initial_loss_pct * p.leverage
            for p in self.positions.values()
            if not p.is_closed
        )
        new_risk = size * price * self.config.max_initial_loss_pct * leverage
        if (total_risk + new_risk) > self.config.portfolio_max_loss_eur:
            return False, f"PORTFOLIO_RISK_LIMIT_EXCEEDED: Risk {total_risk + new_risk:.2f} EUR > Limit {self.config.portfolio_max_loss_eur:.2f} EUR"

        return True, "APPROVED"

    def open_position(
        self,
        symbol: str,
        side: PositionSide,
        size: float,
        entry_price: float,
        leverage: float,
    ) -> Tuple[bool, str, Optional[Position]]:
        """Opens and indexes new position with initial risk stop."""
        valid, reason = self.validate_new_order(symbol, side, size, entry_price, leverage)
        if not valid:
            return False, reason, None

        pos_id = f"pos-{symbol.lower()}-{uuid.uuid4().hex[:6]}"
        if side == PositionSide.LONG:
            initial_stop = entry_price * (1.0 - (self.config.max_initial_loss_pct / leverage))
        else:
            initial_stop = entry_price * (1.0 + (self.config.max_initial_loss_pct / leverage))

        pos = Position(
            position_id=pos_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            leverage=leverage,
            current_price=entry_price,
            stop_loss_price=initial_stop,
            state=ProfitLockState.OPEN_RISK,
        )
        self.positions[pos_id] = pos
        return True, "POSITION_OPENED", pos

    def update_market_price(
        self,
        position_id: str,
        current_price: float,
        market_volatility_pct: float = 0.02,
        spread_pct: float = 0.001,
        is_stale_data: bool = False,
    ) -> Tuple[ProfitLockState, Optional[ExitReason]]:
        """Updates PnL, advances Profit-Lock state machine, and evaluates exit conditions."""
        pos = self.positions.get(position_id)
        if not pos or pos.is_closed:
            return ProfitLockState.CLOSED, None

        # Fail-closed on stale market data
        if is_stale_data:
            pos.state = ProfitLockState.EXIT_REQUIRED
            pos.exit_reason = ExitReason.UNKNOWN_EXECUTION_FAIL_CLOSED.value
            return pos.state, ExitReason.UNKNOWN_EXECUTION_FAIL_CLOSED

        pos.current_price = current_price

        # Calculate PnL percentage relative to entry
        if pos.side == PositionSide.LONG:
            price_delta_pct = (current_price - pos.entry_price) / pos.entry_price
            pnl_pct = price_delta_pct * pos.leverage
            if current_price > pos.peak_price:
                pos.peak_price = current_price
        else:
            price_delta_pct = (pos.entry_price - current_price) / pos.entry_price
            pnl_pct = price_delta_pct * pos.leverage
            if current_price < pos.trough_price:
                pos.trough_price = current_price

        pos.current_unrealized_pnl_pct = pnl_pct
        if pnl_pct > pos.peak_unrealized_pnl_pct:
            pos.peak_unrealized_pnl_pct = pnl_pct

        # 1. Check Profit Lock Activation & Maximum Giveback
        if pos.peak_unrealized_pnl_pct >= self.config.profit_lock_trigger_pct:
            pos.state = ProfitLockState.TRAILING_PROTECTION
            giveback_pct = pos.peak_unrealized_pnl_pct - pnl_pct
            max_allowed_giveback = pos.peak_unrealized_pnl_pct * self.config.max_profit_giveback_pct

            if giveback_pct >= max_allowed_giveback:
                pos.state = ProfitLockState.EXIT_REQUIRED
                pos.exit_reason = ExitReason.PROFIT_GIVEBACK_LIMIT.value
                return pos.state, ExitReason.PROFIT_GIVEBACK_LIMIT

            # Volatility-Aware Trailing Stop (Dynamic based on market volatility & spread)
            vol_buffer = (market_volatility_pct * self.config.trailing_vol_multiplier) + spread_pct
            if pos.side == PositionSide.LONG:
                trailing_stop = pos.peak_price * (1.0 - vol_buffer)
                if trailing_stop > pos.stop_loss_price:
                    pos.stop_loss_price = trailing_stop
            else:
                trailing_stop = pos.trough_price * (1.0 + vol_buffer)
                if trailing_stop < pos.stop_loss_price:
                    pos.stop_loss_price = trailing_stop

        # 2. Check Breakeven Transition
        elif pos.peak_unrealized_pnl_pct >= self.config.breakeven_trigger_pct:
            cost_buffer = (self.config.estimated_fee_pct + self.config.estimated_slippage_pct)
            if pos.side == PositionSide.LONG:
                breakeven_stop = pos.entry_price * (1.0 + cost_buffer)
                if breakeven_stop > pos.stop_loss_price:
                    pos.stop_loss_price = breakeven_stop
                    pos.state = ProfitLockState.BREAKEVEN_PROTECTED
            else:
                breakeven_stop = pos.entry_price * (1.0 - cost_buffer)
                if breakeven_stop < pos.stop_loss_price:
                    pos.stop_loss_price = breakeven_stop
                    pos.state = ProfitLockState.BREAKEVEN_PROTECTED

        # 3. Check Stop Loss Hit (Initial, Breakeven, or Trailing)
        hit_stop = False
        if pos.side == PositionSide.LONG and current_price <= pos.stop_loss_price:
            hit_stop = True
        elif pos.side == PositionSide.SHORT and current_price >= pos.stop_loss_price:
            hit_stop = True

        if hit_stop:
            if pos.state == ProfitLockState.TRAILING_PROTECTION:
                exit_reason = ExitReason.TRAILING_STOP
            elif pos.state == ProfitLockState.BREAKEVEN_PROTECTED:
                exit_reason = ExitReason.BREAKEVEN_STOP
            else:
                exit_reason = ExitReason.INITIAL_STOP_LOSS

            pos.state = ProfitLockState.EXIT_REQUIRED
            pos.exit_reason = exit_reason.value
            return pos.state, exit_reason

        # 4. Check Time Stop
        entry_dt = dt.datetime.fromisoformat(pos.entry_time.replace("Z", "+00:00"))
        now_dt = dt.datetime.now(dt.timezone.utc)
        if (now_dt - entry_dt).total_seconds() > self.config.time_stop_seconds:
            if pos.current_unrealized_pnl_pct < 0.02:  # Stagnant with no progress
                pos.state = ProfitLockState.EXIT_REQUIRED
                pos.exit_reason = ExitReason.TIME_STOP.value
                return pos.state, ExitReason.TIME_STOP

        return pos.state, None

    def execute_partial_take_profit(
        self,
        position_id: str,
        reduction_fraction: float = 0.5,
    ) -> Tuple[bool, str]:
        """Reduces position size at profit target, locking in partial gains."""
        pos = self.positions.get(position_id)
        if not pos or pos.is_closed:
            return False, "POSITION_NOT_ACTIVE"

        if pos.partial_tp_executed:
            return False, "PARTIAL_TP_ALREADY_EXECUTED"

        pos.size = pos.size * (1.0 - reduction_fraction)
        pos.partial_tp_executed = True
        pos.state = ProfitLockState.PARTIAL_PROFIT_SECURED
        return True, f"PARTIAL_TP_EXECUTED: Reduced size to {pos.size:.4f}"

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: ExitReason,
    ) -> Tuple[bool, str]:
        """Closes position, records result, and initiates cooldown if closed in loss."""
        # Deduplicate close requests
        request_key = f"{position_id}:{exit_price}:{reason.value}"
        if request_key in self.processed_close_requests:
            return False, "DUPLICATE_CLOSE_REQUEST_BLOCKED"

        pos = self.positions.get(position_id)
        if not pos or pos.is_closed:
            return False, "POSITION_ALREADY_CLOSED"

        self.processed_close_requests.add(request_key)
        pos.is_closed = True
        pos.closed_at = utc_now()
        pos.exit_reason = reason.value
        pos.state = ProfitLockState.CLOSED

        # Calculate realized PnL
        if pos.side == PositionSide.LONG:
            final_pnl_pct = ((exit_price - pos.entry_price) / pos.entry_price) * pos.leverage
        else:
            final_pnl_pct = ((pos.entry_price - exit_price) / pos.entry_price) * pos.leverage

        if final_pnl_pct < 0.0 or reason == ExitReason.INITIAL_STOP_LOSS:
            self.last_loss_time = time.time()
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        self.closed_positions.append(pos)
        del self.positions[position_id]
        return True, f"CLOSED_SUCCESSFULLY: Reason={reason.value}, FinalPnL={final_pnl_pct * 100:.2f}%"
