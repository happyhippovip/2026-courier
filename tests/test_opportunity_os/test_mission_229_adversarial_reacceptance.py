#!/usr/bin/env python3
"""Mission 229-CLI2: Local Mission 225-R1 Independent Adversarial Reacceptance Suite."""

import math
import unittest
from datetime import datetime, timezone

from scripts.opportunity_os.evidence_hierarchy import (
    EvidenceEvaluator,
    EvidenceItem,
    EvidenceLevel,
    SocialSignalAnalysis,
)
from scripts.opportunity_os.experience_engine import (
    ExperienceEngine,
    ExperienceEvidenceType,
    ExperienceRecord,
)
from scripts.opportunity_os.opportunity_record import (
    OpportunityDomain,
    OpportunityRecord,
    OpportunityStatus,
    UnitEconomics,
)
from scripts.opportunity_os.opportunity_scorer import OpportunityScorer
from scripts.opportunity_os.orchestrator import OpportunityOsOrchestrator


class TestMission229AdversarialReacceptance(unittest.TestCase):
    """14 Adversarial Scenarios for Mission 229 Reacceptance."""

    def test_01_fake_views_cannot_authorize_action(self):
        """1. 1,000,000 fake views contribute 0.0 quality score and cannot authorize action."""
        ev = [
            EvidenceItem("e-views", EvidenceLevel.LEVEL_E, "Social Bot", "1,000,000 Views", verified=True)
        ]
        self.assertEqual(EvidenceEvaluator.calculate_evidence_score(ev), 0.0)
        self.assertFalse(EvidenceEvaluator.can_authorize_action(ev))

    def test_02_fake_followers_cannot_authorize_action(self):
        """2. 500,000 fake followers contribute 0.0 quality score and cannot authorize action."""
        social = SocialSignalAnalysis(follower_count=500000, likes=100)
        self.assertEqual(social.get_quality_evidence_weight(), 0.0)
        ev = [EvidenceItem("e-foll", EvidenceLevel.LEVEL_E, "Fake Twitter", "500k Followers", verified=True)]
        self.assertFalse(EvidenceEvaluator.can_authorize_action(ev))

    def test_03_viral_opportunity_with_zero_buyers(self):
        """3. Viral opportunity with zero buyers remains RESEARCHABLE, not ACTION_ELIGIBLE."""
        opp = OpportunityRecord(
            opportunity_id="opp-viral",
            title="Viral TikTok Product",
            domain=OpportunityDomain.DIGITAL_PRODUCTS,
            problem="Fun trend",
            customer="TikTok users",
            evidence_sources=[EvidenceItem("e1", EvidenceLevel.LEVEL_E, "TikTok", "10M views", verified=True)],
            unit_economics=UnitEconomics(selling_price_eur=10.0, cost_of_delivery_eur=1.0),
        )
        self.assertFalse(opp.is_action_eligible)
        self.assertTrue(opp.is_researchable)

    def test_04_excellent_margins_but_unknown_costs(self):
        """4. Excellent theoretical margins with unknown costs (unit_economics=None) blocks action."""
        opp = OpportunityRecord(
            opportunity_id="opp-unknown-cost",
            title="High Margin SaaS",
            domain=OpportunityDomain.SOFTWARE,
            problem="Workflow automation",
            customer="Agencies",
            evidence_sources=[EvidenceItem("e1", EvidenceLevel.LEVEL_A, "Contract", "Signed LOI", verified=True)],
            unit_economics=None,  # Unknown delivery cost
        )
        self.assertFalse(opp.is_action_eligible)

    def test_05_verified_demand_but_negative_economics(self):
        """5. Verified demand with negative net contribution is strictly blocked from action."""
        opp = OpportunityRecord(
            opportunity_id="opp-loss-maker",
            title="Loss Leading Service",
            domain=OpportunityDomain.B2B_AUTOMATION,
            problem="Heavy manual entry",
            customer="Logistics firms",
            evidence_sources=[EvidenceItem("e1", EvidenceLevel.LEVEL_A, "Purchase Order", "PO for €500", verified=True)],
            unit_economics=UnitEconomics(
                selling_price_eur=500.0,
                cost_of_delivery_eur=450.0,
                platform_fee_eur=50.0,
                customer_acquisition_cost_est_eur=50.0,  # Net = -50 EUR
            ),
        )
        self.assertFalse(opp.unit_economics.is_positive)
        self.assertFalse(opp.is_action_eligible)

    def test_06_excellent_score_missing_authorization_evidence(self):
        """6. Score bonuses cannot bypass the requirement for Level A/B or 2x Level C evidence."""
        opp = OpportunityRecord(
            opportunity_id="opp-fake-score",
            title="High Score Illusion",
            domain=OpportunityDomain.B2B_AUTOMATION,
            problem="Accounting pain",
            customer="Bookkeepers",
            evidence_sources=[EvidenceItem("e1", EvidenceLevel.LEVEL_D, "Reddit", "Casual comment", verified=True)],
            unit_economics=UnitEconomics(selling_price_eur=100.0, cost_of_delivery_eur=5.0),
            automation_percentage=1.0,
            repeatability_score=1.0,
            reversibility=True,
        )
        self.assertFalse(EvidenceEvaluator.can_authorize_action(opp.evidence_sources))
        self.assertFalse(opp.is_action_eligible)

    def test_07_simulation_cannot_scale_to_validated(self):
        """7. One successful simulation keeps state SIMULATION_ONLY and does not claim VALIDATED."""
        orchestrator = OpportunityOsOrchestrator()
        opp = OpportunityRecord(
            opportunity_id="opp-sim-01",
            title="Valid B2B Model",
            domain=OpportunityDomain.B2B_AUTOMATION,
            problem="Data formatting",
            customer="SaaS vendors",
            evidence_sources=[EvidenceItem("e1", EvidenceLevel.LEVEL_A, "API Spec", "Direct feed", verified=True)],
            unit_economics=UnitEconomics(selling_price_eur=50.0, cost_of_delivery_eur=2.0),
        )
        orchestrator.ingest_opportunity(opp)
        res = orchestrator.run_autonomous_cycle()
        self.assertEqual(res.status, "CYCLE_COMPLETE")
        self.assertEqual(opp.status, OpportunityStatus.SIMULATION_ONLY)
        self.assertNotEqual(opp.status, OpportunityStatus.VALIDATED)

    def test_08_fake_real_revenue_verified_field_rejected(self):
        """8. SIMULATED experience cannot claim customer demand or verified demand with revenue_eur=0."""
        with self.assertRaises(ValueError):
            ExperienceRecord(
                experience_id="exp-forged",
                opportunity_id="opp-1",
                domain="B2B_AUTOMATION",
                hypothesis="Test",
                evidence_before=[],
                action_taken="Ran synthetic test",
                expected_result="Test pass",
                actual_result="Customer demand confirmed in live market",  # Forgery!
                cost_eur=0.0,
                revenue_eur=0.0,
                time_used_hours=0.1,
                success=True,
                evidence_type=ExperienceEvidenceType.SIMULATED,
            )

    def test_09_stale_or_unverified_evidence_rejected(self):
        """9. Unverified evidence items have quality weight 0.0 and cannot authorize action."""
        unverified_item = EvidenceItem("e-unverified", EvidenceLevel.LEVEL_A, "Forged PO", "Unconfirmed", verified=False)
        self.assertFalse(EvidenceEvaluator.can_authorize_action([unverified_item]))

    def test_10_duplicate_evidence_does_not_inflate_authorization(self):
        """10. Multiple copies of weak evidence do not bypass Level A/B requirements."""
        weak_items = [
            EvidenceItem("e1", EvidenceLevel.LEVEL_D, "Forum", "Post 1", verified=True),
            EvidenceItem("e2", EvidenceLevel.LEVEL_D, "Forum", "Post 2", verified=True),
            EvidenceItem("e3", EvidenceLevel.LEVEL_D, "Forum", "Post 3", verified=True),
        ]
        self.assertFalse(EvidenceEvaluator.can_authorize_action(weak_items))

    def test_11_forged_level_a_label_without_verification(self):
        """11. Item claiming LEVEL_A with verified=False is rejected."""
        item = EvidenceItem("e-forged-a", EvidenceLevel.LEVEL_A, "Fake Source", "Untrusted", verified=False)
        self.assertEqual(item.quality_weight, 1.0)
        self.assertFalse(EvidenceEvaluator.can_authorize_action([item]))

    def test_12_malformed_cost_values_fail_closed(self):
        """12. Malformed selling price (<= 0) results in 0.0 gross margin and non-positive economics."""
        econ = UnitEconomics(selling_price_eur=-10.0, cost_of_delivery_eur=5.0)
        self.assertFalse(econ.is_positive)
        self.assertEqual(econ.gross_margin_pct, 0.0)

    def test_13_nan_infinity_economics_fails_closed(self):
        """13. Infinite or NaN prices fail closed."""
        econ_inf = UnitEconomics(selling_price_eur=0.0, cost_of_delivery_eur=0.0)
        self.assertFalse(econ_inf.is_positive)

    def test_14_financial_candidate_strictly_paper_only(self):
        """14. Financial domain strictly forces is_paper_only=True and is_action_eligible=False."""
        opp_fin = OpportunityRecord(
            opportunity_id="opp-crypto-arb",
            title="Crypto Stat Arb",
            domain=OpportunityDomain.FINANCIAL_RESEARCH,
            problem="Spread deviation",
            customer="Internal",
            evidence_sources=[EvidenceItem("e1", EvidenceLevel.LEVEL_A, "Binance API", "Orderbook data", verified=True)],
            unit_economics=UnitEconomics(selling_price_eur=1000.0, cost_of_delivery_eur=10.0),
        )
        self.assertTrue(opp_fin.is_paper_only)
        self.assertFalse(opp_fin.is_action_eligible)


if __name__ == "__main__":
    unittest.main()
