"""Comprehensive & Adversarial Test Suite for Opportunity OS (Mission 225-R1).

Covers:
1. Evidence Hierarchy & Strict Social Signal Policy (Quality weight = 0)
2. Opportunity Record & General Domain Support
3. Deterministic Scorer & Dual-Output Daily Question (Research vs Action)
4. Unknown Cost Policy & Gate Enforcement
5. Simulation vs Real Validation Separation
6. Experience Memory Truthfulness (Simulated vs Real)
7. 12 Mandatory Adversarial Tests
"""

import unittest
import os
import shutil
import tempfile
from datetime import datetime, timezone

from scripts.opportunity_os.evidence_hierarchy import (
    EvidenceLevel, EvidenceItem, SocialSignalAnalysis, EvidenceEvaluator
)
from scripts.opportunity_os.opportunity_record import (
    OpportunityRecord, OpportunityDomain, OpportunityStatus, UnitEconomics
)
from scripts.opportunity_os.opportunity_scorer import OpportunityScorer
from scripts.opportunity_os.experience_engine import (
    ExperienceEngine, ExperienceRecord, ExperienceEvidenceType
)
from scripts.opportunity_os.capability_router import CapabilityRouter, CapabilityTask, Capability
from scripts.opportunity_os.lanes import (
    B2bAutomationFactory, EvidenceServiceFactory, PublishingFactory,
    FinancialResearchLab, PatternEvidence
)
from scripts.opportunity_os.orchestrator import OpportunityOsOrchestrator


class TestOpportunityOs(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.exp_engine = ExperienceEngine(storage_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ---------------------------------------------------------
    # Baseline Capabilities & Lanes
    # ---------------------------------------------------------
    def test_social_signal_quality_weight_is_strictly_zero(self):
        social = SocialSignalAnalysis(likes=500000, views=2000000, reposts=100000, follower_count=50000)
        self.assertEqual(social.get_quality_evidence_weight(), 0.0)

    def test_unit_economics_positive_and_negative(self):
        pos = UnitEconomics(selling_price_eur=100.0, cost_of_delivery_eur=10.0, customer_acquisition_cost_est_eur=15.0)
        self.assertTrue(pos.is_positive)
        self.assertEqual(pos.gross_margin_eur, 90.0)

        neg = UnitEconomics(selling_price_eur=50.0, cost_of_delivery_eur=40.0, customer_acquisition_cost_est_eur=20.0)
        self.assertFalse(neg.is_positive)

    def test_capability_router_unit_economics(self):
        router = CapabilityRouter()
        task = CapabilityTask(
            task_id="TASK-UE-1",
            capability=Capability.UNIT_ECONOMICS,
            payload={"price": 199.0, "cost": 15.0, "fee": 5.0, "cac": 20.0}
        )
        res = router.dispatch(task)
        self.assertTrue(res.success)
        self.assertEqual(res.output["net_contribution_eur"], 159.0)

    def test_b2b_factory_templates(self):
        ev = [EvidenceItem("EV-B2B", EvidenceLevel.LEVEL_B, "Verified inquiry", "Order queue", verified=True)]
        opp = B2bAutomationFactory.create_offer("DOCUMENT_PROCESSING", "OPP-DOC", ev)
        self.assertEqual(opp.domain, OpportunityDomain.B2B_AUTOMATION)
        self.assertTrue(opp.is_action_eligible)

    def test_evidence_service_factory(self):
        ev = [EvidenceItem("EV-SVC", EvidenceLevel.LEVEL_B, "Client fact check", "Direct inquiry", verified=True)]
        opp = EvidenceServiceFactory.create_service("COMPETITOR_BRIEF", "OPP-SVC", ev)
        self.assertEqual(opp.domain, OpportunityDomain.RESEARCH_SERVICES)
        self.assertTrue(opp.is_action_eligible)

    def test_publishing_factory(self):
        ev = [EvidenceItem("EV-PUB", EvidenceLevel.LEVEL_B, "KDP keyword volume", "Validated queries", verified=True)]
        opp = PublishingFactory.create_publication("FRUIT_TREES_GARDENING", "OPP-PUB-GARDEN", ev)
        self.assertEqual(opp.domain, OpportunityDomain.PUBLISHING)

    # ---------------------------------------------------------
    # 12 MANDATORY ADVERSARIAL TESTS (Mission 225-R1)
    # ---------------------------------------------------------

    def test_adv_01_level_e_social_hype_only_not_action_eligible(self):
        """1. Level-E social hype only + excellent fake economics -> NOT ACTION_ELIGIBLE, NOT VALIDATED."""
        ev = [EvidenceItem("EV-HYPE", EvidenceLevel.LEVEL_E, "Viral Tweet", "100k likes", verified=True)]
        ue = UnitEconomics(selling_price_eur=1000.0, cost_of_delivery_eur=10.0)
        opp = OpportunityRecord(
            opportunity_id="HYPE-1",
            title="Viral Hype Tool",
            domain=OpportunityDomain.SOFTWARE,
            problem="FOMO",
            customer="Public",
            evidence_sources=ev,
            unit_economics=ue,
            expected_revenue_eur=1000.0
        )
        self.assertFalse(opp.is_action_eligible)
        self.assertNotEqual(opp.status, OpportunityStatus.VALIDATED)

    def test_adv_02_single_weak_level_c_source_not_action_eligible(self):
        """2. One weak Level-C source + excellent economics -> NOT ACTION_ELIGIBLE."""
        ev = [EvidenceItem("EV-C", EvidenceLevel.LEVEL_C, "Blog analysis", "Industry commentary", verified=True)]
        ue = UnitEconomics(selling_price_eur=200.0, cost_of_delivery_eur=10.0)
        opp = OpportunityRecord(
            opportunity_id="WEAK-1",
            title="Speculative Service",
            domain=OpportunityDomain.RESEARCH_SERVICES,
            problem="Lack of analysis",
            customer="Enterprises",
            evidence_sources=ev,
            unit_economics=ue
        )
        self.assertFalse(opp.is_action_eligible)

    def test_adv_03_valid_level_a_with_unknown_unit_economics_is_researchable_only(self):
        """3. Valid Level-A evidence + unknown UnitEconomics -> RESEARCHABLE, NOT ACTION_ELIGIBLE."""
        ev = [EvidenceItem("EV-A", EvidenceLevel.LEVEL_A, "Signed Client Contract", "Audit order", verified=True)]
        opp = OpportunityRecord(
            opportunity_id="UNKNOWN-COST-1",
            title="B2B Workflow",
            domain=OpportunityDomain.B2B_AUTOMATION,
            problem="Process delay",
            customer="Client X",
            evidence_sources=ev,
            unit_economics=None  # Unknown cost!
        )
        self.assertTrue(opp.is_researchable)
        self.assertFalse(opp.is_action_eligible)

    def test_adv_04_all_candidates_negative_scores_yields_none_selected(self):
        """4. All candidates have negative scores -> selected_action_candidate = NONE."""
        ev = [EvidenceItem("EV-1", EvidenceLevel.LEVEL_E, "Rumor", "Unverified", verified=True)]
        opp1 = OpportunityRecord("NEG-1", "Trap 1", OpportunityDomain.OTHER_LAWFUL, "Prob", "Cust", ev, legal_risk=0.9)
        opp2 = OpportunityRecord("NEG-2", "Trap 2", OpportunityDomain.OTHER_LAWFUL, "Prob", "Cust", ev, fraud_risk=0.5)

        answer = OpportunityScorer.answer_daily_question([opp1, opp2])
        self.assertIsNone(answer["best_action_eligible_candidate"])
        self.assertEqual(answer["status"], "NO_ACTION_ELIGIBLE_CANDIDATE")

    def test_adv_05_pool_non_empty_no_candidate_passes_evidence_gate(self):
        """5. Pool non-empty but no candidate passes evidence gate -> NO_VIABLE_CANDIDATE."""
        ev_hype = [EvidenceItem("EV-H", EvidenceLevel.LEVEL_E, "Hype", "Views", verified=True)]
        opp = OpportunityRecord(
            "BAD-POOL", "Hype Product", OpportunityDomain.DIGITAL_PRODUCTS, "P", "C",
            evidence_sources=ev_hype,
            unit_economics=UnitEconomics(10.0, 1.0)
        )
        orch = OpportunityOsOrchestrator(experience_engine=self.exp_engine)
        orch.ingest_opportunity(opp)
        res = orch.run_autonomous_cycle()
        self.assertEqual(res.status, "NO_ACTION_ELIGIBLE_CANDIDATE")
        self.assertIsNone(res.top_action_id)

    def test_adv_06_synthetic_simulation_cannot_set_validated_status(self):
        """6. Synthetic test + positive UnitEconomics + revenue_eur = 0 -> SIMULATION_ONLY, NOT VALIDATED."""
        ev = [EvidenceItem("EV-A", EvidenceLevel.LEVEL_A, "Contract", "Primary data", verified=True)]
        opp = B2bAutomationFactory.create_offer("EMAIL_TRIAGE_AUTOMATION", "SIM-OPP", ev)
        
        orch = OpportunityOsOrchestrator(experience_engine=self.exp_engine)
        orch.ingest_opportunity(opp)
        res = orch.run_autonomous_cycle()

        self.assertEqual(opp.status, OpportunityStatus.SIMULATION_ONLY)
        self.assertNotEqual(opp.status, OpportunityStatus.VALIDATED)

    def test_adv_07_synthetic_simulation_must_not_claim_customer_demand_verified(self):
        """7. Synthetic simulation must NOT create: CUSTOMER_DEMAND_VERIFIED = TRUE."""
        ev = [EvidenceItem("EV-A", EvidenceLevel.LEVEL_A, "Contract", "Primary data", verified=True)]
        opp = B2bAutomationFactory.create_offer("LEAD_QUALIFICATION", "DEMAND-CHECK", ev)
        orch = OpportunityOsOrchestrator(experience_engine=self.exp_engine)
        orch.ingest_opportunity(opp)
        orch.run_autonomous_cycle()

        self.assertFalse(opp.customer_demand_verified)
        self.assertFalse(opp.revenue_verified)

    def test_adv_08_experience_memory_records_simulated_evidence_type(self):
        """8. Experience memory after simulation must identify: EVIDENCE_TYPE = SIMULATED."""
        ev = [EvidenceItem("EV-A", EvidenceLevel.LEVEL_A, "Contract", "Primary data", verified=True)]
        opp = B2bAutomationFactory.create_offer("DOCUMENT_PROCESSING", "EXP-CHECK", ev)
        orch = OpportunityOsOrchestrator(experience_engine=self.exp_engine)
        orch.ingest_opportunity(opp)
        res = orch.run_autonomous_cycle()

        lessons = self.exp_engine.query_lessons(domain="B2B_AUTOMATION")
        self.assertTrue(len(lessons) >= 1)
        self.assertEqual(lessons[0].evidence_type, ExperienceEvidenceType.SIMULATED)
        self.assertEqual(lessons[0].revenue_eur, 0.0)

    def test_adv_09_prohibits_fake_demand_claims_in_simulated_experience(self):
        """Strict check: ExperienceRecord post-init throws if simulated experience claims verified demand."""
        with self.assertRaises(ValueError):
            ExperienceRecord(
                experience_id="FAKE-EXP",
                opportunity_id="OPP-1",
                domain="B2B",
                hypothesis="Test",
                evidence_before=[],
                action_taken="Simulation",
                expected_result="Test",
                actual_result="Verified demand confirmed", # FORBIDDEN in SIMULATED!
                cost_eur=0.0,
                revenue_eur=0.0,
                time_used_hours=1.0,
                success=True,
                evidence_type=ExperienceEvidenceType.SIMULATED,
                lesson="Customer demand verified"          # FORBIDDEN in SIMULATED!
            )

    def test_adv_10_financial_research_strictly_paper_only_no_live_action(self):
        """10. Financial opportunity with excellent paper statistics -> PAPER_ONLY, no live-action eligibility."""
        lab = FinancialResearchLab()
        pat = PatternEvidence("PAT-BTC", "BTC", "DISLOCATION", 50, 0.70, 0.02, 0.01, True, ["BULL", "BEAR", "RANGE"])
        lab.record_pattern(pat)
        res = lab.evaluate_financial_candidate("PAT-BTC")
        self.assertFalse(res["authorized_for_live"])
        self.assertEqual(res["mode"], "PAPER_ONLY")

        # In record model:
        fin_opp = OpportunityRecord("FIN-1", "BTC Sniper", OpportunityDomain.FINANCIAL_RESEARCH, "Spread", "Lab")
        self.assertTrue(fin_opp.is_paper_only)
        self.assertFalse(fin_opp.is_action_eligible)

    def test_adv_11_score_manipulation_cannot_bypass_evidence_authorization(self):
        """11. Score manipulation (large automation/reversibility bonuses) cannot bypass evidence authorization."""
        # No Level A/B evidence
        ev_weak = [EvidenceItem("EV-W", EvidenceLevel.LEVEL_D, "Forum post", "Thread", verified=True)]
        opp = OpportunityRecord(
            opportunity_id="BONUS-INFLATED",
            title="Inflated Score Candidate",
            domain=OpportunityDomain.B2B_AUTOMATION,
            problem="P",
            customer="C",
            evidence_sources=ev_weak,
            automation_percentage=1.0,
            repeatability_score=1.0,
            reversibility=True,
            unit_economics=UnitEconomics(500.0, 5.0)
        )
        score = OpportunityScorer.score_opportunity(opp)
        self.assertGreater(score, 20.0) # Composite score is boosted by bonuses
        # BUT action eligibility MUST remain False!
        self.assertFalse(opp.is_action_eligible)

    def test_adv_12_unknown_costs_strictly_block_action_authorization(self):
        """12. Unknown costs + otherwise perfect score -> no action authorization."""
        ev_perfect = [
            EvidenceItem("EV-1", EvidenceLevel.LEVEL_A, "Contract", "Real deal", verified=True),
            EvidenceItem("EV-2", EvidenceLevel.LEVEL_A, "Bank statement", "Audited cash", verified=True)
        ]
        opp = OpportunityRecord(
            opportunity_id="PERFECT-UNKNOWN-COST",
            title="Great Idea Unknown Delivery Cost",
            domain=OpportunityDomain.B2B_AUTOMATION,
            problem="P",
            customer="C",
            evidence_sources=ev_perfect,
            unit_economics=None # Unknown delivery cost!
        )
        self.assertFalse(opp.is_action_eligible)


if __name__ == "__main__":
    unittest.main()
