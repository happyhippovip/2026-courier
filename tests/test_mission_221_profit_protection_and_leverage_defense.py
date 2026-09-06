#!/usr/bin/env python3
"""Mission 221 Acceptance Test Suite: Profit Protection & Leverage Defense."""

import unittest
from scripts.leverage_defense_risk_engine import (
    ExitReason,
    LeverageDefenseRiskEngine,
    PositionSide,
    ProfitLockState,
    RiskConfig,
)


class TestMission221ProfitProtectionAndLeverageDefense(unittest.TestCase):
    def setUp(self):
        # Default Canary Config: Max 1X leverage
        self.config = RiskConfig(
            max_canary_leverage=1.0,
            max_initial_loss_pct=0.05,
            breakeven_trigger_pct=0.10,
            profit_lock_trigger_pct=0.20,
            max_profit_giveback_pct=0.35,
            portfolio_max_loss_eur=10.0,
            cooldown_period_seconds=300,
        )
        self.engine = LeverageDefenseRiskEngine(config=self.config)

    def test_01_sndk_profit_giveback_protection(self):
        """SNDK-like trade reaches +28% profit, then retracing triggers profit-giveback limit."""
        # Open 1X Long at $100
        ok, reason, pos = self.engine.open_position("SNDK", PositionSide.LONG, size=1.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)

        # Market rallies to $128 (+28% PnL) -> Profit Lock Activates
        st, exit_r = self.engine.update_market_price(pos.position_id, current_price=128.0)
        self.assertEqual(st, ProfitLockState.TRAILING_PROTECTION)
        self.assertIsNone(exit_r)
        self.assertEqual(pos.peak_unrealized_pnl_pct, 0.28)

        # Market retraces to $115 (+15% PnL, giveback of 13% > max allowed 9.8%)
        st2, exit_r2 = self.engine.update_market_price(pos.position_id, current_price=115.0)
        self.assertEqual(st2, ProfitLockState.EXIT_REQUIRED)
        self.assertEqual(exit_r2, ExitReason.PROFIT_GIVEBACK_LIMIT)

    def test_02_brent_short_50pct_reversal_protection(self):
        """Brent-like short reaches +50% profit, then reversal triggers profit lock exit."""
        ok, reason, pos = self.engine.open_position("BRENT", PositionSide.SHORT, size=1.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)

        # Price drops to $50 (+50% Short PnL)
        st, exit_r = self.engine.update_market_price(pos.position_id, current_price=50.0)
        self.assertEqual(st, ProfitLockState.TRAILING_PROTECTION)
        self.assertIsNone(exit_r)

        # Price bounces to $75 (+25% PnL, 25% giveback exceeds 35% of 50% = 17.5% threshold)
        st2, exit_r2 = self.engine.update_market_price(pos.position_id, current_price=75.0)
        self.assertEqual(st2, ProfitLockState.EXIT_REQUIRED)
        self.assertEqual(exit_r2, ExitReason.PROFIT_GIVEBACK_LIMIT)

    def test_03_spacex_long_initial_stop_loss_trigger(self):
        """SpaceX-like long keeps falling and triggers initial stop loss without delay."""
        ok, reason, pos = self.engine.open_position("SPACEX", PositionSide.LONG, size=1.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)
        self.assertEqual(pos.stop_loss_price, 95.0)  # 5% initial stop

        # Price drops to $94
        st, exit_r = self.engine.update_market_price(pos.position_id, current_price=94.0)
        self.assertEqual(st, ProfitLockState.EXIT_REQUIRED)
        self.assertEqual(exit_r, ExitReason.INITIAL_STOP_LOSS)

    def test_04_canary_high_leverage_strict_denial(self):
        """10X, 20X, and 40X positions are strictly denied by Canary Leverage Policy."""
        ok_10x, r_10x = self.engine.validate_new_order("SNDK", PositionSide.LONG, 1.0, 100.0, leverage=10.0)
        self.assertFalse(ok_10x)
        self.assertIn("CANARY_LEVERAGE_DENIED", r_10x)

        ok_20x, r_20x = self.engine.validate_new_order("OIL", PositionSide.SHORT, 1.0, 100.0, leverage=20.0)
        self.assertFalse(ok_20x)
        self.assertIn("CANARY_LEVERAGE_DENIED", r_20x)

        ok_40x, r_40x = self.engine.validate_new_order("BTC", PositionSide.SHORT, 1.0, 100.0, leverage=40.0)
        self.assertFalse(ok_40x)
        self.assertIn("CANARY_LEVERAGE_DENIED", r_40x)

    def test_05_portfolio_risk_limit_prevents_multi_loss_cascade(self):
        """Portfolio max loss limit blocks new trades when cumulative risk reaches threshold."""
        # Open 2 positions
        ok1, _, _ = self.engine.open_position("SYM1", PositionSide.LONG, size=1.0, entry_price=80.0, leverage=1.0)  # Risk = 4 EUR
        self.assertTrue(ok1)
        ok2, _, _ = self.engine.open_position("SYM2", PositionSide.LONG, size=1.0, entry_price=80.0, leverage=1.0)  # Risk = 4 EUR
        self.assertTrue(ok2)

        # Third position would exceed portfolio limit of 10 EUR (Total = 12 EUR)
        ok3, reason3, _ = self.engine.open_position("SYM3", PositionSide.LONG, size=1.0, entry_price=80.0, leverage=1.0)
        self.assertFalse(ok3)
        self.assertIn("PORTFOLIO_RISK_LIMIT_EXCEEDED", reason3)

    def test_06_partial_take_profit_staged_reduction(self):
        """Partial take-profit reduces exposure without increasing risk."""
        ok, _, pos = self.engine.open_position("SNDK", PositionSide.LONG, size=2.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)

        # Execute 50% partial take-profit
        tp_ok, tp_msg = self.engine.execute_partial_take_profit(pos.position_id, reduction_fraction=0.5)
        self.assertTrue(tp_ok)
        self.assertEqual(pos.size, 1.0)
        self.assertEqual(pos.state, ProfitLockState.PARTIAL_PROFIT_SECURED)

        # Duplicate TP attempt is rejected
        tp_dup, _ = self.engine.execute_partial_take_profit(pos.position_id, reduction_fraction=0.5)
        self.assertFalse(tp_dup)

    def test_07_duplicate_close_request_deduplication(self):
        """Close requests are deduplicated exactly once."""
        ok, _, pos = self.engine.open_position("BTC", PositionSide.LONG, size=1.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)

        # First close succeeds
        c1, msg1 = self.engine.close_position(pos.position_id, exit_price=105.0, reason=ExitReason.TAKE_PROFIT_TARGET)
        self.assertTrue(c1)

        # Second identical close request is blocked
        c2, msg2 = self.engine.close_position(pos.position_id, exit_price=105.0, reason=ExitReason.TAKE_PROFIT_TARGET)
        self.assertFalse(c2)
        self.assertIn("DUPLICATE_CLOSE_REQUEST_BLOCKED", msg2)

    def test_08_breakeven_protection_includes_fees_and_slippage(self):
        """Breakeven protection adjusts stop above entry + fees + slippage."""
        ok, _, pos = self.engine.open_position("OIL", PositionSide.LONG, size=1.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)

        # Price reaches +10% ($110) -> Breakeven triggers
        st, _ = self.engine.update_market_price(pos.position_id, current_price=110.0)
        self.assertEqual(st, ProfitLockState.BREAKEVEN_PROTECTED)
        # Expected stop = 100 * (1 + 0.001 fee + 0.002 slippage) = 100.30
        self.assertGreater(pos.stop_loss_price, 100.0)
        self.assertAlmostEqual(pos.stop_loss_price, 100.30, places=2)

    def test_09_stale_market_data_fails_closed(self):
        """Stale market data during position monitoring fails closed immediately."""
        ok, _, pos = self.engine.open_position("TEST", PositionSide.LONG, size=1.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)

        # Update with stale flag
        st, exit_r = self.engine.update_market_price(pos.position_id, current_price=102.0, is_stale_data=True)
        self.assertEqual(st, ProfitLockState.EXIT_REQUIRED)
        self.assertEqual(exit_r, ExitReason.UNKNOWN_EXECUTION_FAIL_CLOSED)

    def test_10_no_revenge_trading_cooldown_enforced(self):
        """Revenge trading / immediate flip after stop loss is strictly blocked by cooldown."""
        ok, _, pos = self.engine.open_position("SNDK", PositionSide.LONG, size=1.0, entry_price=100.0, leverage=1.0)
        self.assertTrue(ok)

        # Trigger stop loss exit
        self.engine.close_position(pos.position_id, exit_price=94.0, reason=ExitReason.INITIAL_STOP_LOSS)

        # Immediate re-order attempt on same or other symbol is rejected
        rev_ok, rev_reason, _ = self.engine.open_position("SNDK", PositionSide.SHORT, size=1.0, entry_price=94.0, leverage=1.0)
        self.assertFalse(rev_ok)
        self.assertIn("COOLDOWN_ACTIVE", rev_reason)


if __name__ == "__main__":
    unittest.main()
