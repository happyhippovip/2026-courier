import unittest
import sys, os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.market_defense.opsec_policy import OpsecPolicy, SocialMediaFilter, TradingState, DisclosureClass, PostingVerdict

class TestOpsecPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = OpsecPolicy()
        self.filter = SocialMediaFilter(self.policy)

    def test_detects_long_short_keywords(self):
        leaks = self.policy.scan_text_for_leaks('I went long BTC at 65000')
        self.assertIn(DisclosureClass.POSITION_SIZE, leaks)

    def test_detects_entry_price(self):
        leaks = self.policy.scan_text_for_leaks('entered at 65000')
        self.assertIn(DisclosureClass.ENTRY_PRICE, leaks)

    def test_detects_stop_loss(self):
        leaks = self.policy.scan_text_for_leaks('stop loss at 64000')
        self.assertIn(DisclosureClass.STOP_LOSS, leaks)

    def test_detects_liquidation(self):
        leaks = self.policy.scan_text_for_leaks('liquidation price at 60000')
        self.assertIn(DisclosureClass.LIQUIDATION_PRICE, leaks)

    def test_detects_take_profit(self):
        leaks = self.policy.scan_text_for_leaks('take profit at 70000')
        self.assertIn(DisclosureClass.TAKE_PROFIT, leaks)

    def test_detects_leverage(self):
        leaks = self.policy.scan_text_for_leaks('using 10x leverage')
        self.assertIn(DisclosureClass.LEVERAGE, leaks)

    def test_detects_eth_wallet(self):
        leaks = self.policy.scan_text_for_leaks('0x742d35Cc6634C0532925a3b844Bc9e7595f2bD61')
        self.assertIn(DisclosureClass.WALLET_ADDRESS, leaks)

    def test_detects_btc_wallet(self):
        leaks = self.policy.scan_text_for_leaks('bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh')
        self.assertIn(DisclosureClass.WALLET_ADDRESS, leaks)

    def test_detects_budget(self):
        leaks = self.policy.scan_text_for_leaks('$500 budget')
        self.assertIn(DisclosureClass.BUDGET_AMOUNT, leaks)

    def test_clean_text_no_leaks(self):
        leaks = self.policy.scan_text_for_leaks('Great weather today!')
        self.assertEqual(len(leaks), 0)

    def test_blocks_posting_with_open_position(self):
        state = TradingState(open_positions=['BTC_LONG'], closed_positions={}, trading_account_ids=[], wallet_fragments=[])
        res = self.filter.filter_outbound('hello', state)
        self.assertEqual(res.verdict, PostingVerdict.BLOCK_POSITION_OPEN)

    def test_blocks_posting_before_delay(self):
        state = TradingState(open_positions=[], closed_positions={'pos1': datetime.now(timezone.utc) - timedelta(hours=1)}, trading_account_ids=[], wallet_fragments=[])
        res = self.filter.filter_outbound('hello', state)
        self.assertEqual(res.verdict, PostingVerdict.BLOCK_DELAY_REQUIRED)

    def test_allows_posting_after_delay(self):
        state = TradingState(open_positions=[], closed_positions={'pos1': datetime.now(timezone.utc) - timedelta(hours=25)}, trading_account_ids=[], wallet_fragments=[])
        res = self.filter.filter_outbound('hello', state)
        self.assertEqual(res.verdict, PostingVerdict.ALLOW)

    def test_trading_id_separation_passes(self):
        self.assertTrue(self.policy.check_trading_public_id_separation(['id1'], 'clean text'))

    def test_trading_id_separation_fails(self):
        self.assertFalse(self.policy.check_trading_public_id_separation(['id1'], 'has id1 in it'))

    def test_social_media_filter_blocks_wallet_fragment(self):
        state = TradingState(open_positions=[], closed_positions={}, trading_account_ids=[], wallet_fragments=['abcd'])
        res = self.filter.filter_outbound('my wallet is abcd', state)
        self.assertEqual(res.verdict, PostingVerdict.BLOCK_SENSITIVE_DATA)

    def test_social_media_filter_allows_clean(self):
        state = TradingState(open_positions=[], closed_positions={}, trading_account_ids=[], wallet_fragments=[])
        res = self.filter.filter_outbound('all good', state)
        self.assertEqual(res.verdict, PostingVerdict.ALLOW)

    def test_social_media_filter_blocks_account_id_in_content(self):
        state = TradingState(open_positions=[], closed_positions={}, trading_account_ids=['acc123'], wallet_fragments=[])
        res = self.filter.filter_outbound('my acc is acc123', state)
        self.assertEqual(res.verdict, PostingVerdict.BLOCK_SENSITIVE_DATA)

if __name__ == '__main__':
    unittest.main()
