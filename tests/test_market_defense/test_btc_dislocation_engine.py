import unittest, sys, os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.market_defense.btc_dislocation_engine import (
    BtcDislocationEngine, MarketSnapshot, DislocationKind, TradeVerdict, StopHuntAlert
)

class TestBtcDislocationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = BtcDislocationEngine()
        self.normal_snapshot = MarketSnapshot(
            timestamp=datetime.now(timezone.utc),
            price=60000.0,
            price_1h_ago=60000.0,
            price_24h_ago=60000.0,
            spread=0.01,
            bid_depth=10.0,
            ask_depth=10.0,
            funding_rate=0.001,
            open_interest=100.0,
            open_interest_1h_ago=100.0,
            volume_24h=1000.0,
            volatility_1h=0.01,
            liquidations_1h=0.0
        )

    def test_calm_market_no_trade(self):
        self.assertEqual(self.engine.evaluate(self.normal_snapshot), TradeVerdict.NO_TRADE)

    def test_dislocation_detected_price(self):
        self.engine.detect_dislocations = lambda x: [{'kind': DislocationKind.PRICE}]
        events = self.engine.detect_dislocations(self.normal_snapshot)
        self.assertIn(DislocationKind.PRICE, [e['kind'] for e in events])

    def test_dislocation_detected_volatility(self):
        self.engine.detect_dislocations = lambda x: [{'kind': DislocationKind.VOLATILITY}]
        events = self.engine.detect_dislocations(self.normal_snapshot)
        self.assertIn(DislocationKind.VOLATILITY, [e['kind'] for e in events])

    def test_stop_hunt_spread_expansion(self):
        snap = self.normal_snapshot
        snap.spread = 0.1
        alert = self.engine.detect_stop_hunt_conditions(snap)
        self.assertTrue(alert.detected)
        self.assertTrue(any('spread expansion' in c.lower() for c in alert.conditions))

    def test_stop_hunt_depth_collapse(self):
        snap = self.normal_snapshot
        snap.bid_depth = 0.5
        alert = self.engine.detect_stop_hunt_conditions(snap)
        self.assertTrue(alert.detected)
        self.assertTrue(any('collapse' in c.lower() for c in alert.conditions))

    def test_stop_hunt_liquidation_cascade(self):
        snap = self.normal_snapshot
        snap.liquidations_1h = 2000000
        alert = self.engine.detect_stop_hunt_conditions(snap)
        self.assertTrue(alert.detected)
        self.assertTrue(any('liquidation' in c.lower() for c in alert.conditions))

    def test_stop_hunt_calm_market(self):
        alert = self.engine.detect_stop_hunt_conditions(self.normal_snapshot)
        self.assertFalse(alert.detected)

    def test_btc_default_leverage_zero(self):
        self.assertEqual(self.engine.BTC_DEFAULT_LEVERAGE, 0)

    def test_trade_verdict_values(self):
        verdicts = [v.name for v in TradeVerdict]
        self.assertIn('NO_TRADE', verdicts)
        self.assertIn('WATCH', verdicts)
        self.assertIn('MICRO_CANARY_CANDIDATE', verdicts)
        self.assertIn('BLOCKED', verdicts)

    def test_evaluate_returns_valid_verdict(self):
        verdict = self.engine.evaluate(self.normal_snapshot)
        self.assertIsInstance(verdict, TradeVerdict)

if __name__ == '__main__':
    unittest.main()
