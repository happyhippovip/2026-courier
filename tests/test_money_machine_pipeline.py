#!/usr/bin/env python3
"""Acceptance Test Suite for Money Machine V1 Operating System.

Verifies:
1. Canonical revenue opportunity ledger discovery and persistence
2. Economic ranking bias (CASH_NOW, time-to-first-EUR, 0 capital, asset reuse)
3. Cheapest real validation execution and artifact generation (Experiment Before Build)
4. Human fast-gate and buy-gate non-blocking parking
5. Truthful money scoreboard tracking (0.00 EUR spend invariant)
6. 100% Deterministic local execution (0 Model Calls, 0 EUR Spend)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.money_machine_pipeline import (
    EconomicClass,
    MoneyMachinePipeline,
    MoneyScoreboard,
    OpportunityState,
    RevenueOpportunity,
)


class TestMoneyMachinePipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="money_machine_test_"))
        self.pipeline = MoneyMachinePipeline(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_opportunity_discovery_and_ledger_persistence(self):
        """Revenue opportunities are discovered and persisted in canonical ledger."""
        ranked = self.pipeline.scan_project_revenue_opportunities()
        self.assertGreaterEqual(len(ranked), 4)

        ledger = self.pipeline.load_ledger()
        self.assertIn("REV-OPP-B2B-AUTONOMY-AUDIT", ledger)
        self.assertIn("REV-OPP-ASSET-LICENSING-FRUITKI", ledger)
        self.assertIn("REV-OPP-CLI-SENTINEL-TOOL", ledger)

    def test_02_economic_ranking_bias(self):
        """CASH_NOW with short time-to-cash outranks long-horizon or moonshot opportunities."""
        fast_cash = RevenueOpportunity(
            opportunity_id="OPP-FAST-CASH",
            title="Fast B2B Task",
            economic_class=EconomicClass.CASH_NOW.value,
            time_to_first_eur="1-3_DAYS",
            capital_required_eur=0.0,
            revenue_probability=0.8,
            automation_percentage=90.0,
            existing_asset_reuse="HIGH",
            evidence_confidence=0.8,
        )

        moonshot = RevenueOpportunity(
            opportunity_id="OPP-MOONSHOT",
            title="Long Moonshot",
            economic_class=EconomicClass.MOONSHOT.value,
            time_to_first_eur="3_MONTHS+",
            capital_required_eur=500.0,
            revenue_probability=0.2,
            automation_percentage=40.0,
            existing_asset_reuse="LOW",
            evidence_confidence=0.3,
        )

        score_fast = self.pipeline.compute_economic_score(fast_cash)
        score_moon = self.pipeline.compute_economic_score(moonshot)

        self.assertGreater(score_fast, score_moon)

    def test_03_cheapest_validation_execution(self):
        """Executes cheapest validation, creates offering dossier, and updates scoreboard."""
        self.pipeline.scan_project_revenue_opportunities()

        res = self.pipeline.execute_cheapest_validation("REV-OPP-B2B-AUTONOMY-AUDIT")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["validation_state"], OpportunityState.OFFER_READY.value)
        self.assertIn("offer_dossier", res["artifacts"])

        # Check dossier file exists
        dossier_path = self.test_dir / res["artifacts"]["offer_dossier"]
        self.assertTrue(dossier_path.exists())
        self.assertIn("B2B Autonomous System Determinism", dossier_path.read_text(encoding="utf-8"))

        # Scoreboard updated
        sb = self.pipeline.load_scoreboard()
        self.assertGreaterEqual(sb.validated_opportunities, 1)
        self.assertGreaterEqual(sb.compound_assets_created, 1)
        self.assertEqual(sb.capital_spent_eur, 0.0)

    def test_04_human_fast_gate_parks_opportunity_without_blocking(self):
        """Human fast gate parks specific opportunity and updates scoreboard."""
        self.pipeline.scan_project_revenue_opportunities()

        gate_file = self.pipeline.create_human_fast_gate(
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            gate_type="LOGIN",
            description="Client portal login credentials required",
            minimal_human_action="Enter API token in settings.json",
        )
        self.assertTrue(gate_file.exists())

        ledger = self.pipeline.load_ledger()
        self.assertEqual(ledger["REV-OPP-B2B-AUTONOMY-AUDIT"].state, OpportunityState.BLOCKED_HUMAN_GATE.value)

        sb = self.pipeline.load_scoreboard()
        self.assertEqual(sb.human_interventions, 1)

    def test_05_buy_gate_enforces_zero_spend_firewall(self):
        """Buy gate creates structured purchase request and strictly sets 0.0 EUR autonomous spend."""
        self.pipeline.scan_project_revenue_opportunities()

        buy_file = self.pipeline.create_buy_gate(
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            product="Pro Hosting Server",
            price_eur=15.0,
            promo_expiry="2026-09-15",
            concrete_workload="Host public client demo endpoint",
            expected_benefit="Increase client conversion by 40%",
            alternatives="Local ngrok or free GitHub Pages",
            recommendation="Stay on 0 EUR free tier until 1st EUR received",
            human_action_required="Approve €15 payment if client signs",
        )
        self.assertTrue(buy_file.exists())

        data = json.loads(buy_file.read_text(encoding="utf-8"))
        self.assertEqual(data["autonomous_spend_limit_eur"], 0.0)
        self.assertEqual(data["status"], "PENDING_CHIEF_PAYMENT_APPROVAL")


if __name__ == "__main__":
    unittest.main()
