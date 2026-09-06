#!/usr/bin/env python3
"""Mission 226 Acceptance Test Suite: Daily Evidence Scout & Opportunity Ranker."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.daily_evidence_scout import (
    DailyEvidenceScout,
    OpportunityCandidate,
    OpportunityDomain,
    Reversibility,
    RiskLevel,
)


class TestMission226DailyEvidenceScout(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m226_scout_"))
        self.evidence_dir = self.test_dir / "events" / "evidence-ledger"
        self.runtime_dir = self.test_dir / "events" / "runtime-state"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        self.scout = DailyEvidenceScout(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_social_metrics_do_not_count_as_primary_evidence(self):
        """Social vanity metrics (likes/views) are flagged as HYPE/INORGANIC and penalized."""
        sig1 = self.scout.normalize_evidence_signal(
            source_uri="https://twitter.com/post/123",
            source_type="SOCIAL_METRIC",
            signal_text="Viral post with 50,000 likes talking about AI tools",
            likes_or_followers_count=50000,
        )
        self.assertFalse(sig1.is_primary_source)
        self.assertEqual(sig1.social_metric_flag, "HYPE")

        sig2 = self.scout.normalize_evidence_signal(
            source_uri="https://upwork.com/job/456",
            source_type="PRIMARY_BUYER_REQUEST",
            signal_text="Client requesting automated invoice processing pipeline, budget $1500",
        )
        self.assertTrue(sig2.is_primary_source)
        self.assertIsNone(sig2.social_metric_flag)

    def test_02_structured_candidate_schema_complete(self):
        """Opportunity Candidate contains all required contract fields."""
        cand_data = {
            "title": "B2B Invoice Automation Service",
            "domain": OpportunityDomain.B2B_AUTOMATION.value,
            "startup_cost_eur": 0.0,
            "time_to_test": "1 day",
            "time_to_revenue": "3 days",
            "unit_economics_confidence": 0.90,
            "automation_fit": 0.95,
            "reversibility": Reversibility.HIGH.value,
            "risk": RiskLevel.LOW.value,
            "next_cheap_test": "Cold outreach with simulated proof-of-concept output",
        }
        signals = [
            self.scout.normalize_evidence_signal("client-1", "PRIMARY_BUYER_REQUEST", "Need invoice parser"),
            self.scout.normalize_evidence_signal("client-2", "PRIMARY_BUYER_REQUEST", "Looking for recurring bookkeeping bot"),
            self.scout.normalize_evidence_signal("job-board", "PUBLIC_JOB_BOARD", "Python automation specialist required"),
        ]
        cand = self.scout.evaluate_and_score_candidate(cand_data, signals)

        self.assertEqual(cand.evidence_count, 3)
        self.assertEqual(cand.primary_source_count, 3)
        self.assertEqual(cand.startup_cost_eur, 0.0)
        self.assertGreaterEqual(cand.overall_confidence_score, 0.85)
        self.assertTrue(bool(cand.fingerprint))

    def test_03_daily_top_three_ranking_selection(self):
        """Scout selects Top 1 Low Risk, Top 2 Low Risk, and Top 3 Long Term Option."""
        cands = [
            OpportunityCandidate(
                opportunity_id="opp-1",
                title="Top Low Risk B2B",
                domain=OpportunityDomain.B2B_AUTOMATION,
                evidence_count=4,
                primary_source_count=4,
                demand_evidence=[],
                startup_cost_eur=0.0,
                time_to_test="1 day",
                time_to_revenue="2 days",
                unit_economics_confidence=0.9,
                automation_fit=0.9,
                reversibility=Reversibility.HIGH,
                risk=RiskLevel.LOW,
                next_cheap_test="Outreach test",
                overall_confidence_score=0.92,
            ),
            OpportunityCandidate(
                opportunity_id="opp-2",
                title="Second Low Risk Freelance",
                domain=OpportunityDomain.FREELANCE_DEMAND,
                evidence_count=3,
                primary_source_count=3,
                demand_evidence=[],
                startup_cost_eur=10.0,
                time_to_test="2 days",
                time_to_revenue="5 days",
                unit_economics_confidence=0.85,
                automation_fit=0.8,
                reversibility=Reversibility.HIGH,
                risk=RiskLevel.LOW,
                next_cheap_test="Proposal test",
                overall_confidence_score=0.84,
            ),
            OpportunityCandidate(
                opportunity_id="opp-3",
                title="Longer Term Digital Product",
                domain=OpportunityDomain.DIGITAL_PRODUCTS,
                evidence_count=2,
                primary_source_count=2,
                demand_evidence=[],
                startup_cost_eur=20.0,
                time_to_test="3 days",
                time_to_revenue="14 days",
                unit_economics_confidence=0.8,
                automation_fit=0.85,
                reversibility=Reversibility.HIGH,
                risk=RiskLevel.LOW,
                next_cheap_test="Landing page canary",
                overall_confidence_score=0.80,
            ),
        ]
        for c in cands:
            c.fingerprint = c.calculate_fingerprint()

        rankings = self.scout.rank_daily_opportunities(cands)
        self.assertIsNotNone(rankings.top_1_low_risk_revenue)
        self.assertEqual(rankings.top_1_low_risk_revenue["opportunity_id"], "opp-1")

        self.assertIsNotNone(rankings.top_2_low_risk_revenue)
        self.assertEqual(rankings.top_2_low_risk_revenue["opportunity_id"], "opp-2")

        self.assertIsNotNone(rankings.top_3_longer_term_option)
        self.assertEqual(rankings.top_3_longer_term_option["opportunity_id"], "opp-3")

        # Zero spend and model calls
        self.assertEqual(rankings.model_calls_used, 0)
        self.assertEqual(rankings.spend_eur, 0.0)

    def test_04_wake_builder_only_on_new_high_confidence_opportunity(self):
        """Wakes builder only on confidence >= 0.85 with new fingerprint."""
        cands = [
            OpportunityCandidate(
                opportunity_id="opp-high-1",
                title="High Confidence Enterprise Sync",
                domain=OpportunityDomain.B2B_AUTOMATION,
                evidence_count=5,
                primary_source_count=5,
                demand_evidence=[],
                startup_cost_eur=0.0,
                time_to_test="1 day",
                time_to_revenue="3 days",
                unit_economics_confidence=0.95,
                automation_fit=0.95,
                reversibility=Reversibility.HIGH,
                risk=RiskLevel.LOW,
                next_cheap_test="Demo video and direct pitch",
                overall_confidence_score=0.95,
            )
        ]
        cands[0].fingerprint = cands[0].calculate_fingerprint()

        # First run: finds new high confidence
        rank1 = self.scout.rank_daily_opportunities(cands)
        self.assertTrue(rank1.new_high_confidence_found)

        # Second run with same candidate: no re-wake (deduplicated)
        rank2 = self.scout.rank_daily_opportunities(cands)
        self.assertFalse(rank2.new_high_confidence_found)

    def test_05_deterministic_ledger_ingestion_and_zero_spend(self):
        """Full cycle loads ledger files, ranks, and writes state with 0 spend."""
        fixture_path = self.evidence_dir / "sample_opp.json"
        fixture_path.write_text(json.dumps({
            "opportunity_id": "opp-ledger-01",
            "title": "Local SEO Verification Service",
            "domain": "LOCAL_SERVICES",
            "startup_cost_eur": 0.0,
            "unit_economics_confidence": 0.85,
            "automation_fit": 0.90,
            "raw_signals": [
                {"source_uri": "gmaps-query", "source_type": "PRIMARY_BUYER_REQUEST", "signal_text": "Local audit request"}
            ]
        }))

        rankings = self.scout.run_evidence_scout_cycle()
        self.assertEqual(len(rankings.all_ranked_candidates), 1)
        self.assertEqual(rankings.spend_eur, 0.0)
        self.assertEqual(rankings.model_calls_used, 0)
        self.assertTrue(self.scout.ranking_file.exists())


if __name__ == "__main__":
    unittest.main()
