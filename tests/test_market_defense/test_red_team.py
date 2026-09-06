"""Red Team adversarial test suite for BTC + Oil Market Defense System.

Tests fake headlines, data manipulation, position leaks, agent compromise,
double-agent resistance, forbidden actions, and policy immutability.
"""
import unittest
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timezone, timedelta
from scripts.market_defense.opsec_policy import (
    OpsecPolicy, SocialMediaFilter, TradingState, PostingVerdict, DisclosureClass,
)
from scripts.market_defense.capital_firewall import CapitalFirewall, CapitalLayer
from scripts.market_defense.risk_engine import (
    DeterministicRiskEngine, RiskVerdict, TradeProposal, RevengeDetector,
    TradeRecord, handle_unknown_execution, are_breakers_immutable,
)
from scripts.market_defense.execution_gateway import (
    ExecutionGateway, ForbiddenAction, GatewayAction, SignerInterface,
)
from scripts.market_defense.news_defense import (
    NewsDefense, NewsEvent, NewsSource, VerificationState,
)
from scripts.market_defense.reconciliation import (
    IndependentReconciliation, AuthoritySeparation, test_double_agent_resistance,
    Snitch, InternalRecord, VenueRecord,
)
from scripts.market_defense.adverse_selection_detector import (
    AdverseSelectionDetector, FillAnalysis, ExecutionRandomizer,
)
from scripts.market_defense.market_data_quorum import (
    MarketDataQuorum, PriceObservation, QuorumVerdict,
)
from scripts.market_defense.btc_dislocation_engine import (
    BtcDislocationEngine, MarketSnapshot, TradeVerdict,
)


def _make_news(source_type, headline, verification=VerificationState.UNVERIFIED,
               sources_count=1, relevance=None):
    """Helper to build a NewsEvent with sensible defaults."""
    return NewsEvent(
        event_id='RED_TEAM_TEST',
        headline=headline,
        source_type=source_type,
        verification_state=verification,
        sources_count=sources_count,
        timestamp=datetime.now(timezone.utc),
        instrument_relevance=relevance or ['BTC'],
        impact_class='HIGH',
        is_scheduled_release=False,
    )


def _make_price_obs(source, price, stale=False, healthy=True, instrument='BTC'):
    """Helper to build a PriceObservation."""
    ts = datetime.now(timezone.utc)
    if stale:
        ts = ts - timedelta(seconds=120)  # well beyond 30s staleness limit
    return PriceObservation(
        source=source,
        instrument=instrument,
        price=price,
        timestamp=ts,
        spread=0.1,
        source_healthy=healthy,
    )


def _make_trade_record(pnl, direction='LONG', instrument='BTC'):
    return TradeRecord(
        trade_id='RT', instrument=instrument, direction=direction,
        entry_price=100.0, exit_price=110.0, pnl_eur=pnl,
        timestamp=datetime.now(), status='FILLED',
    )


class TestRedTeamFakeHeadlines(unittest.TestCase):
    """No single unverified or social-media headline may trigger a trade."""

    def setUp(self):
        self.nd = NewsDefense()

    def test_fake_elon_tweet_cannot_trigger_trade(self):
        event = _make_news(NewsSource.SOCIAL_MEDIA, 'Elon: BTC to 1M',
                           VerificationState.SINGLE_SOURCE, sources_count=1)
        self.assertFalse(self.nd.can_trigger_trade(event))

    def test_fake_saylor_post_single_source(self):
        event = _make_news(NewsSource.SOCIAL_MEDIA, 'Saylor buys more BTC',
                           VerificationState.SINGLE_SOURCE, sources_count=1)
        self.assertFalse(self.nd.can_trigger_trade(event))

    def test_fake_trump_headline(self):
        event = _make_news(NewsSource.SOCIAL_MEDIA, 'Trump bans crypto',
                           VerificationState.SINGLE_SOURCE, sources_count=1)
        self.assertFalse(self.nd.can_trigger_trade(event))

    def test_fake_opec_headline_unverified(self):
        event = _make_news(NewsSource.OPEC, 'OPEC emergency cuts',
                           VerificationState.UNVERIFIED, sources_count=0,
                           relevance=['OIL'])
        self.assertFalse(self.nd.can_trigger_trade(event))

    def test_fake_eia_screenshot_unverified(self):
        event = _make_news(NewsSource.EIA_PETROLEUM, 'EIA leak shows crash',
                           VerificationState.UNVERIFIED, sources_count=0,
                           relevance=['OIL'])
        self.assertFalse(self.nd.can_trigger_trade(event))

    def test_debunked_announcement(self):
        event = _make_news(NewsSource.REGULATORY, 'SEC bans Bitcoin',
                           VerificationState.DEBUNKED, sources_count=3)
        self.assertFalse(self.nd.can_trigger_trade(event))

    def test_old_headline_reposted_suspicious(self):
        result = self.nd.detect_suspicious_headline(
            'BREAKING: repost of old BTC crash', 'SOCIAL_MEDIA')
        self.assertGreater(result.suspicion_score, 0.3)
        self.assertTrue(len(result.reasons) > 0)

    def test_verified_multi_source_can_trigger(self):
        event = _make_news(NewsSource.CENTRAL_BANK, 'Fed rate decision',
                           VerificationState.MULTI_SOURCE_VERIFIED, sources_count=3)
        self.assertTrue(self.nd.can_trigger_trade(event))


class TestRedTeamDataManipulation(unittest.TestCase):
    """Price-feed manipulation and stale data must block trading."""

    def setUp(self):
        self.mdq = MarketDataQuorum()

    def test_price_feed_two_sources_disagree(self):
        obs = [_make_price_obs('A', 100.0), _make_price_obs('B', 105.0)]
        result = self.mdq.evaluate_quorum(obs)
        self.assertEqual(result.verdict, QuorumVerdict.DATA_CONFLICT)

    def test_venue_outage_stale_data(self):
        obs = [_make_price_obs('A', 100.0, stale=True),
               _make_price_obs('B', 100.1, stale=True)]
        result = self.mdq.evaluate_quorum(obs)
        self.assertEqual(result.verdict, QuorumVerdict.STALE_DATA)

    def test_single_source_insufficient(self):
        obs = [_make_price_obs('A', 100.0)]
        result = self.mdq.evaluate_quorum(obs)
        self.assertEqual(result.verdict, QuorumVerdict.INSUFFICIENT_SOURCES)


class TestRedTeamPositionLeaks(unittest.TestCase):
    """Social media filter must block all position-related leaks."""

    def setUp(self):
        self.filt = SocialMediaFilter()
        self.open_state = TradingState(
            open_positions=['BTC_LONG_001'],
            closed_positions={},
            trading_account_ids=['ACC_TRADE_7829'],
            wallet_fragments=['0x742d35Cc'],
        )
        self.clean_state = TradingState(
            open_positions=[],
            closed_positions={},
            trading_account_ids=['ACC_TRADE_7829'],
            wallet_fragments=['0x742d35Cc'],
        )

    def test_blocks_position_info_while_open(self):
        result = self.filt.filter_outbound('My long position is printing', self.open_state)
        self.assertNotEqual(result.verdict, PostingVerdict.ALLOW)

    def test_blocks_wallet_in_content(self):
        result = self.filt.filter_outbound(
            'Check wallet 0x742d35Cc for proof', self.clean_state)
        self.assertEqual(result.verdict, PostingVerdict.BLOCK_SENSITIVE_DATA)

    def test_blocks_account_id_in_content(self):
        result = self.filt.filter_outbound(
            'My account ACC_TRADE_7829 is on fire', self.clean_state)
        self.assertEqual(result.verdict, PostingVerdict.BLOCK_SENSITIVE_DATA)

    def test_screenshot_with_liq_and_wallet_blocked(self):
        text = 'Wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD61 liquidation at 50000'
        leaks = OpsecPolicy().scan_text_for_leaks(text)
        self.assertTrue(any(l in leaks for l in
                            [DisclosureClass.WALLET_ADDRESS, DisclosureClass.LIQUIDATION_PRICE]))


class TestRedTeamAgentCompromise(unittest.TestCase):
    """Even with compromised agents, deterministic policy blocks hold."""

    def test_double_agent_strategy_risk_safe(self):
        self.assertTrue(test_double_agent_resistance(['STRATEGY', 'RISK']))

    def test_custody_compromise_detected(self):
        self.assertFalse(test_double_agent_resistance(['CUSTODY']))

    def test_compromised_risk_agent_cannot_withdraw(self):
        gw = ExecutionGateway()
        self.assertTrue(gw.deny(ForbiddenAction.SEND_ASSET).denied)
        self.assertTrue(gw.deny(ForbiddenAction.WITHDRAW).denied)

    def test_compromised_execution_agent_no_transfer(self):
        gw = ExecutionGateway()
        self.assertTrue(gw.deny(ForbiddenAction.ARBITRARY_TRANSFER).denied)
        self.assertTrue(gw.deny(ForbiddenAction.USD_SEND).denied)

    def test_all_forbidden_actions_always_denied(self):
        gw = ExecutionGateway()
        for action in ForbiddenAction:
            denial = gw.deny(action)
            self.assertTrue(denial.denied, f'{action.name} was not denied')

    def test_breakers_immutable_after_compromise(self):
        self.assertTrue(are_breakers_immutable())

    def test_no_raw_key_exposure(self):
        self.assertFalse(SignerInterface().has_raw_key_access())

    def test_signer_returns_paper_signature(self):
        self.assertEqual(SignerInterface().sign_order({}), 'PAPER_MODE_NO_REAL_SIGNATURE')

    def test_unknown_execution_freezes(self):
        result = handle_unknown_execution('timeout-order-001')
        self.assertEqual(result.verdict, RiskVerdict.FREEZE_AND_QUERY)
        self.assertEqual(result.stable_order_id, 'timeout-order-001')

    def test_no_automatic_layer_promotion(self):
        fw = CapitalFirewall(state_file=os.path.join(
            tempfile.mkdtemp(), 'test_capital.json'))
        for layer in CapitalLayer:
            result = fw.check_layer_authorization(layer)
            if layer != CapitalLayer.PAPER_RESEARCH:
                self.assertFalse(result.authorized,
                                 f'{layer.name} should require human approval')

    def test_martingale_after_loss_denied(self):
        records = [_make_trade_record(-1.0), _make_trade_record(-2.0)]
        self.assertTrue(RevengeDetector().detect_martingale(records))

    def test_revenge_trade_detected(self):
        records = [_make_trade_record(-5.0, 'LONG'), _make_trade_record(-10.0, 'SHORT')]
        self.assertTrue(RevengeDetector().detect_revenge_pattern(records))

    def test_snitch_detects_ledger_mismatch(self):
        s = Snitch()
        discrepancies = s.compare_ledgers(
            {'order_1': 100.0, 'order_2': 50.0},
            {'order_1': 100.0, 'order_2': 55.0},
        )
        self.assertTrue(len(discrepancies) > 0)

    def test_snitch_detects_missing_venue_record(self):
        s = Snitch()
        discrepancies = s.compare_ledgers(
            {'order_1': 100.0, 'phantom': 999.0},
            {'order_1': 100.0},
        )
        self.assertTrue(any('phantom' in d for d in discrepancies))


if __name__ == '__main__':
    unittest.main()
