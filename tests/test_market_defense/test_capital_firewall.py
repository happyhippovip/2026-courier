import unittest, sys, os, tempfile, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.market_defense.capital_firewall import CapitalFirewall, CapitalLayer

class TestCapitalFirewall(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, 'state.json')
        self.firewall = CapitalFirewall(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initial_budget_is_35(self):
        self.assertEqual(self.firewall.get_remaining_budget(), 35.0)

    def test_reserve_within_limit(self):
        res = self.firewall.reserve_budget(1.5, 'agent1')
        self.assertEqual(res.status, 'APPROVED')

    def test_reserve_exceeds_single_limit(self):
        res = self.firewall.reserve_budget(3.0, 'agent1')
        self.assertEqual(res.status, 'DENIED')

    def test_budget_exhaustion(self):
        for _ in range(17):
            self.firewall.reserve_budget(2.0, 'agent1')
        res = self.firewall.reserve_budget(2.0, 'agent1')
        self.assertEqual(res.status, 'BUDGET_EXHAUSTED')

    def test_release_reservation_updates_budget(self):
        res = self.firewall.reserve_budget(1.0, 'agent1')
        self.firewall.release_reservation(res.reservation_id, -1.0)
        self.assertEqual(self.firewall.get_remaining_budget(), 34.0)

    def test_layer_paper_authorized(self):
        res = self.firewall.check_layer_authorization(CapitalLayer.PAPER_RESEARCH)
        self.assertTrue(res.authorized)

    def test_layer_micro_canary_not_auto(self):
        res = self.firewall.check_layer_authorization(CapitalLayer.MICRO_CANARY)
        self.assertFalse(res.authorized)

    def test_layer_100k_not_auto(self):
        res = self.firewall.check_layer_authorization(CapitalLayer.LIVE_100K)
        self.assertFalse(res.authorized)

    def test_layer_600k_not_auto(self):
        res = self.firewall.check_layer_authorization(CapitalLayer.LIVE_600K)
        self.assertFalse(res.authorized)

    def test_circuit_breaker_per_trade(self):
        res = self.firewall.check_circuit_breakers(3.0, [])
        self.assertEqual(res.status, 'TRIPPED')

    def test_circuit_breaker_consecutive(self):
        res = self.firewall.check_circuit_breakers(1.0, [1.0, 1.0, 1.0])
        self.assertEqual(res.status, 'TRIPPED')

    def test_circuit_breaker_pass(self):
        res = self.firewall.check_circuit_breakers(1.0, [])
        self.assertEqual(res.status, 'PASS')

    def test_martingale_detected(self):
        self.assertTrue(self.firewall.detect_martingale([{'pnl': -1, 'size': 1}, {'pnl': -1, 'size': 2}]))

    def test_martingale_not_detected(self):
        self.assertFalse(self.firewall.detect_martingale([{'pnl': -1, 'size': 1}, {'pnl': 1, 'size': 1}]))

if __name__ == '__main__':
    unittest.main()
