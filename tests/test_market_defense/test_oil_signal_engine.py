"""Tests for the Oil Signal Engine."""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timezone
from scripts.market_defense.oil_signal_engine import (
    OilSignalEngine, OilLivePolicy, OilSnapshot, OilPreLiveProof, OilInstrument,
)


def _make_snapshot(**overrides):
    """Create a default balanced OilSnapshot with optional overrides."""
    defaults = dict(
        timestamp=datetime.now(timezone.utc),
        wti_price=70.0, brent_price=75.0,
        front_month_price=70.0, next_month_price=71.0,
        contango_backwardation=1.0, inventory_surprise_pct=0.0,
        refinery_utilization_pct=90.0, gasoline_stocks_delta=0.0,
        distillate_stocks_delta=0.0, us_production_mbpd=12.5,
        imports_exports_delta=0.0, opec_supply_signal=0.0,
        shipping_disruption_active=False, refinery_outage_active=False,
        pipeline_outage_active=False, geopolitical_shock_active=False,
        natgas_price=3.0, usd_index=100.0,
    )
    defaults.update(overrides)
    return OilSnapshot(**defaults)


def _make_proof(all_true=True, **overrides):
    """Create OilPreLiveProof with all fields True or selectively overridden."""
    defaults = dict(
        exact_instrument=all_true, maximum_possible_loss=all_true,
        no_physical_delivery=all_true, no_unbounded_margin=all_true,
        expiry_guard=all_true, auto_close_before_dangerous_window=all_true,
        roll_policy=all_true, fee_model=all_true, slippage_model=all_true,
    )
    defaults.update(overrides)
    return OilPreLiveProof(**defaults)


class TestOilSignalEngine(unittest.TestCase):

    def setUp(self):
        self.engine = OilSignalEngine()

    def test_oil_live_is_deny(self):
        self.assertFalse(self.engine.is_live_authorized())

    def test_oil_paper_allowed(self):
        self.assertEqual(self.engine.OIL_PAPER_POLICY, OilLivePolicy.ALLOW)

    def test_oil_live_policy_deny(self):
        self.assertEqual(self.engine.OIL_LIVE_POLICY, OilLivePolicy.DENY)

    def test_evaluate_oil_returns_result(self):
        result = self.engine.evaluate_oil(_make_snapshot())
        self.assertTrue(hasattr(result, 'verdict'))
        self.assertTrue(hasattr(result, 'bullish_score'))
        self.assertTrue(hasattr(result, 'bearish_score'))

    def test_pre_live_all_true_passes(self):
        proof = _make_proof(all_true=True)
        self.assertTrue(self.engine.check_pre_live_requirements(proof))

    def test_pre_live_no_physical_delivery_fails(self):
        proof = _make_proof(no_physical_delivery=False)
        self.assertFalse(self.engine.check_pre_live_requirements(proof))

    def test_pre_live_no_expiry_guard_fails(self):
        proof = _make_proof(expiry_guard=False)
        self.assertFalse(self.engine.check_pre_live_requirements(proof))

    def test_pre_live_no_unbounded_margin_fails(self):
        proof = _make_proof(no_unbounded_margin=False)
        self.assertFalse(self.engine.check_pre_live_requirements(proof))

    def test_oil_instruments(self):
        self.assertEqual(OilInstrument.WTI.value, 'WTI')
        self.assertEqual(OilInstrument.BRENT.value, 'BRENT')

    def test_snapshot_fields(self):
        snap = _make_snapshot(wti_price=72.5, brent_price=77.0)
        self.assertEqual(snap.wti_price, 72.5)
        self.assertEqual(snap.brent_price, 77.0)

    def test_oil_live_never_authorized_this_build(self):
        for _ in range(5):
            self.assertFalse(OilSignalEngine().is_live_authorized())

    def test_evaluate_no_trade_on_balanced(self):
        result = self.engine.evaluate_oil(_make_snapshot())
        self.assertIn(result.verdict, ['NO_TRADE', 'WATCH'])


if __name__ == '__main__':
    unittest.main()
