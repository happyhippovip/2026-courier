#!/usr/bin/env python3
"""Mission 228 Acceptance Test Suite: Future Revenue Backlog & Zero-Spend Evidence Scout."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.future_revenue_backlog_engine import (
    CandidateDomain,
    CandidateProfile,
    FailurePreventionPair,
    FutureRevenueBacklogEngine,
    LaunchPacket,
    ValidationState,
)


class TestMission228FutureRevenueBacklog(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m228_backlog_"))
        self.engine = FutureRevenueBacklogEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_candidate_22_field_schema_and_fingerprinting(self):
        """Validates that candidate profiles support the comprehensive 22-field evidence schema."""
        cand = CandidateProfile(
            candidate_id="cand-b2b-01",
            title="Automated PDF/Invoice Reconciliation Bot",
            domain=CandidateDomain.B2B_AUTOMATION,
            problem="Accounting teams spend 15 hours/week matching PDF invoices against bank feeds",
            buyer="Mid-market accounting managers & CFOs",
            primary_evidence=["Job posting on Upwork seeking custom OCR script", "Direct interview with SMB accountant"],
            secondary_evidence=["Reddit r/accounting discussions on month-end close delays"],
            current_alternatives=["Manual copy-paste into Excel", "Expensive enterprise OCR packages ($500+/mo)"],
            competitors=["DocuParse", "Rossum"],
            pricing="99 EUR / month flat or 1.50 EUR / batch",
            customer_pain="High error rate and tedious manual entry causing delayed payroll",
            market_demand="High recurring requirement across small business service sector",
            startup_cost_eur=0.0,
            delivery_cost_eur=0.02,
            platform_fees_pct=0.03,
            time_to_first_revenue="2 days",
            expected_margin_pct=95.0,
            automation_fit=0.95,
            human_work_required="Zero after setup; automated error webhook review if OCR ambiguity",
            legal_risk="LOW",
            platform_risk="LOW",
            failure_modes=["OCR hallucination on scanned receipts", "Client changing invoice formats"],
            why_others_fail="They overcharge enterprise prices and require complex sales calls",
            what_we_can_do_better="Lightweight local Python parser with instant deterministic proof output",
            next_zero_cost_test="Simulate invoice parsing on 20 public test fixtures and send sample output to requester",
            validation_state=ValidationState.DEMAND_EVIDENCE_FOUND,
        )
        is_new = self.engine.register_or_update_candidate(cand)
        self.assertTrue(is_new)
        self.assertTrue(bool(cand.fingerprint))
        self.assertEqual(cand.validation_state, ValidationState.DEMAND_EVIDENCE_FOUND)

    def test_02_failure_prevention_library_mapping(self):
        """Validates that 3 common failures map to 3 concrete preventions in failure_pattern_library.json."""
        cand = CandidateProfile(
            candidate_id="cand-data-01",
            title="Local Business Schema Verifier",
            domain=CandidateDomain.DATA_PRODUCTS,
            problem="Local businesses lose SEO rankings due to broken schema markup",
            buyer="Local service business owners",
            primary_evidence=["Public audit showing 42% of local contractors have broken Schema.org tags"],
            secondary_evidence=[],
            current_alternatives=["Manual validator tool"],
            competitors=["SchemaApp"],
            pricing="49 EUR / audit",
            customer_pain="Invisible drop in Google Maps search placement",
            market_demand="Consistent local SEO demand",
            startup_cost_eur=0.0,
            delivery_cost_eur=0.0,
            platform_fees_pct=0.0,
            time_to_first_revenue="1 day",
            expected_margin_pct=99.0,
            automation_fit=0.98,
            human_work_required="None",
            legal_risk="LOW",
            platform_risk="LOW",
            failure_modes=["Client ignores audit", "False positive schema warning"],
            why_others_fail="Deliver generic 40-page PDF reports that clients never read",
            what_we_can_do_better="One-page visual summary with 1-click copy-paste JSON-LD fix",
            next_zero_cost_test="Generate sample fix report for 5 public sites",
            validation_state=ValidationState.TEST_READY,
            failure_prevention=FailurePreventionPair(
                common_failure_1="Overly technical reports confusing non-technical business owners",
                our_prevention_1="Generate clean one-page executive summary with green/red status indicators",
                common_failure_2="Client unable to implement code fix",
                our_prevention_2="Provide ready-to-paste script tag snippet with instructions for standard CMSs",
                common_failure_3="Platform dependency on third party APIs",
                our_prevention_3="Use standard local Python schema validator without paid API dependencies",
            ),
        )
        self.engine.register_or_update_candidate(cand)
        library = self.engine.build_failure_library()

        self.assertIn("cand-data-01", library)
        self.assertEqual(len(library["cand-data-01"]["common_failures"]), 3)
        self.assertEqual(len(library["cand-data-01"]["our_preventions"]), 3)
        self.assertTrue(self.engine.failure_library_file.exists())

    def test_03_future_launch_packet_generation(self):
        """Generates structured launch packets with status READY_TO_TEST_LATER without publishing or spending."""
        packet = LaunchPacket(
            packet_id="packet-b2b-01",
            candidate_id="cand-b2b-01",
            offer_description="Deterministic Invoice Parsing & Reconciliation Automation",
            target_customer="Accounting agencies and SMB bookkeepers",
            demo_plan="30-second screen capture demonstrating batch invoice ingestion into clean CSV",
            sample_deliverable="Sample reconciled spreadsheet with highlighted variances",
            price_hypothesis="99 EUR / month flat",
            unit_economics={"cost_per_run_eur": 0.01, "price_per_month_eur": 99.0, "gross_margin_pct": 99.0},
            delivery_workflow=["Ingest PDF batch", "Deterministic OCR & table extraction", "Validate totals", "Export clean CSV"],
            qa_checklist=["Verify mathematical precision to 2 decimal places", "Ensure no hallucinated line items"],
            security_checklist=["Local processing only", "No customer invoice data transmitted to external servers"],
            customer_onboarding=["Provide webhook endpoint", "Upload sample vendor invoice"],
            success_metrics={"target_conversion_rate": 0.15, "target_churn_rate": 0.05},
            status="READY_TO_TEST_LATER",
        )
        cand = CandidateProfile(
            candidate_id="cand-b2b-01",
            title="Invoice Bot",
            domain=CandidateDomain.B2B_AUTOMATION,
            problem="Manual invoice entry",
            buyer="Bookkeepers",
            primary_evidence=["Job post"],
            secondary_evidence=[],
            current_alternatives=[],
            competitors=[],
            pricing="99 EUR",
            customer_pain="Time waste",
            market_demand="High",
            startup_cost_eur=0.0,
            delivery_cost_eur=0.01,
            platform_fees_pct=0.0,
            time_to_first_revenue="2 days",
            expected_margin_pct=99.0,
            automation_fit=0.95,
            human_work_required="Low",
            legal_risk="LOW",
            platform_risk="LOW",
            failure_modes=[],
            why_others_fail="",
            what_we_can_do_better="",
            next_zero_cost_test="Demo run",
            launch_packet=packet,
        )
        self.engine.register_or_update_candidate(cand)
        readiness = self.engine.build_launch_readiness()

        self.assertIn("cand-b2b-01", readiness)
        self.assertEqual(readiness["cand-b2b-01"]["status"], "READY_TO_TEST_LATER")
        self.assertTrue(self.engine.launch_readiness_file.exists())

    def test_04_top_3_pipeline_and_research_only_ranking(self):
        """Produces Top 1 Fastest, Top 2 Repeatable, Top 3 Long Term, and Top Research Only."""
        c1 = CandidateProfile(
            candidate_id="c1",
            title="Fast Local Service Audit",
            domain=CandidateDomain.LOCAL_SERVICES,
            problem="P1", buyer="B1", primary_evidence=["E1", "E2"], secondary_evidence=[],
            current_alternatives=[], competitors=[], pricing="49 EUR", customer_pain="", market_demand="",
            startup_cost_eur=0.0, delivery_cost_eur=0.0, platform_fees_pct=0.0, time_to_first_revenue="1 day",
            expected_margin_pct=99.0, automation_fit=0.95, human_work_required="Low", legal_risk="LOW", platform_risk="LOW",
            failure_modes=[], why_others_fail="", what_we_can_do_better="", next_zero_cost_test="",
        )
        c2 = CandidateProfile(
            candidate_id="c2",
            title="B2B Workflow Automation",
            domain=CandidateDomain.B2B_AUTOMATION,
            problem="P2", buyer="B2", primary_evidence=["E1", "E2", "E3"], secondary_evidence=[],
            current_alternatives=[], competitors=[], pricing="199 EUR/mo", customer_pain="", market_demand="",
            startup_cost_eur=0.0, delivery_cost_eur=0.5, platform_fees_pct=0.0, time_to_first_revenue="3 days",
            expected_margin_pct=95.0, automation_fit=0.90, human_work_required="Low", legal_risk="LOW", platform_risk="LOW",
            failure_modes=[], why_others_fail="", what_we_can_do_better="", next_zero_cost_test="",
        )
        c3 = CandidateProfile(
            candidate_id="c3",
            title="Enterprise Software Utility",
            domain=CandidateDomain.SOFTWARE,
            problem="P3", buyer="B3", primary_evidence=["E1"], secondary_evidence=[],
            current_alternatives=[], competitors=[], pricing="499 EUR/mo", customer_pain="", market_demand="",
            startup_cost_eur=0.0, delivery_cost_eur=1.0, platform_fees_pct=0.0, time_to_first_revenue="14 days",
            expected_margin_pct=90.0, automation_fit=0.85, human_work_required="Low", legal_risk="LOW", platform_risk="LOW",
            failure_modes=[], why_others_fail="", what_we_can_do_better="", next_zero_cost_test="",
        )
        c_fin = CandidateProfile(
            candidate_id="c_fin",
            title="Oil/Brent Spread Statistical Arbitrage Paper Lab",
            domain=CandidateDomain.FINANCIAL_RESEARCH_PAPER_ONLY,
            problem="Commodity spread mean reversion study", buyer="Internal Research", primary_evidence=["Historical tick data"], secondary_evidence=[],
            current_alternatives=[], competitors=[], pricing="N/A", customer_pain="", market_demand="",
            startup_cost_eur=0.0, delivery_cost_eur=0.0, platform_fees_pct=0.0, time_to_first_revenue="N/A",
            expected_margin_pct=0.0, automation_fit=1.0, human_work_required="Zero", legal_risk="LOW", platform_risk="LOW",
            failure_modes=["Slippage", "Execution latency"], why_others_fail="", what_we_can_do_better="", next_zero_cost_test="Backtest on 60 days of tick data",
        )

        for c in [c1, c2, c3, c_fin]:
            self.engine.register_or_update_candidate(c)

        pipeline = self.engine.generate_top_3_pipeline()

        self.assertIsNotNone(pipeline["top_1_fastest_low_risk_revenue"])
        self.assertEqual(pipeline["top_1_fastest_low_risk_revenue"]["candidate_id"], "c1")

        self.assertIsNotNone(pipeline["top_2_best_repeatable_revenue"])
        self.assertEqual(pipeline["top_2_best_repeatable_revenue"]["candidate_id"], "c2")

        self.assertIsNotNone(pipeline["top_3_best_long_term_asset"])
        self.assertEqual(pipeline["top_3_best_long_term_asset"]["candidate_id"], "c3")

        self.assertIsNotNone(pipeline["top_research_only"])
        self.assertEqual(pipeline["top_research_only"]["candidate_id"], "c_fin")

        # Invariants strictly preserved
        self.assertEqual(pipeline["spend_eur"], 0.0)
        self.assertEqual(pipeline["model_calls_used"], 0)

    def test_05_durable_state_persistence_across_all_5_files(self):
        """Validates that all 5 durable state files are correctly created and structured."""
        self.engine.persist_all_state()

        self.assertTrue(self.engine.backlog_file.exists())
        self.assertTrue(self.engine.ranking_file.exists())
        self.assertTrue(self.engine.fingerprints_file.exists())
        self.assertTrue(self.engine.failure_library_file.exists())
        self.assertTrue(self.engine.launch_readiness_file.exists())


if __name__ == "__main__":
    unittest.main()
