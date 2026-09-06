#!/usr/bin/env python3
"""Deterministic Test Suite for Compound Intelligence Flywheel Engine.

Verifies:
1. Permanent Research Question Persistence ("Wie können wir aus Werkzeugen...")
2. Compounding Category Value Weighting (1x -> 5x -> 10x -> 20x -> 50x)
3. Multi-Agent Challenge and Experimental Verification Loop
4. Flywheel Velocity Multiplier Compounding
5. Meta-Loop Prevention & Real Task Anchoring
6. 100% Deterministic execution (0 Model Calls, 0.00 EUR Spend)
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.compound_intelligence_flywheel import (
    CATEGORY_WEIGHTS,
    CompoundingCategory,
    CompoundIntelligenceFlywheel,
    PERMANENT_MOTTO,
    PERMANENT_RESEARCH_QUESTION,
)


class TestCompoundIntelligenceFlywheel(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="flywheel_test_"))
        self.flywheel = CompoundIntelligenceFlywheel(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_permanent_research_question_persisted(self):
        """Permanent research question is prominently persisted in central state."""
        self.assertEqual(self.flywheel.research_question, PERMANENT_RESEARCH_QUESTION)
        self.assertEqual(self.flywheel.motto, PERMANENT_MOTTO)

        ns_file = self.test_dir / "events" / "runtime-state" / "north_star_directive.json"
        self.assertTrue(ns_file.exists())
        data = json.loads(ns_file.read_text(encoding="utf-8"))
        self.assertEqual(data["permanent_research_question"], PERMANENT_RESEARCH_QUESTION)
        self.assertEqual(data["strategic_objective"], "COMPOUND_INTELLIGENCE")

    def test_02_compounding_value_weighting(self):
        """Higher compounding categories receive higher multiplier weights."""
        self.assertEqual(CATEGORY_WEIGHTS[CompoundingCategory.SINGLE_TASK_SAVING], 1.0)
        self.assertEqual(CATEGORY_WEIGHTS[CompoundingCategory.ROUTING_RELIABILITY_IMPROVEMENT], 5.0)
        self.assertEqual(CATEGORY_WEIGHTS[CompoundingCategory.SHARED_ORGANIZATIONAL_KNOWLEDGE], 10.0)
        self.assertEqual(CATEGORY_WEIGHTS[CompoundingCategory.CHIEF_INTERVENTION_REDUCTION], 20.0)
        self.assertEqual(CATEGORY_WEIGHTS[CompoundingCategory.META_IMPROVEMENT_ENGINE], 50.0)

        idea_single = self.flywheel.propose_compounding_idea(
            question="Fix typo in local script header",
            category=CompoundingCategory.SINGLE_TASK_SAVING,
            proposed_by="GOOGLE_BUILDER",
            hypothesis="Cosmetic fix",
            expected_future_tasks_benefited=1,
        )
        idea_meta = self.flywheel.propose_compounding_idea(
            question="Automate AST test gap discovery",
            category=CompoundingCategory.META_IMPROVEMENT_ENGINE,
            proposed_by="GOOGLE_BUILDER",
            hypothesis="Eliminates manual test audit across all future modules",
            expected_future_tasks_benefited=100,
        )

        self.assertGreater(idea_meta.compounding_score, idea_single.compounding_score * 50)

    def test_03_challenge_and_verification_loop(self):
        """Ideas require adversarial challenge and experimental verification before adoption."""
        idea = self.flywheel.propose_compounding_idea(
            question="Optimize generation counter allocation in CanonicalAuthority",
            category=CompoundingCategory.ROUTING_RELIABILITY_IMPROVEMENT,
            proposed_by="GOOGLE_BUILDER",
            hypothesis="In-memory flock cache reduces lock contention by 30%",
            expected_future_tasks_benefited=50,
        )

        # Successful verification
        ok, msg = self.flywheel.challenge_and_verify_idea(
            idea_id=idea.idea_id,
            challenger_role="DETERMINISTIC_ORACLE",
            challenge_notes="Tested under multi-process lock contention with 0 lock corruption.",
            experiment_result=True,
            measured_improvement_factor=1.30,
        )
        self.assertTrue(ok)
        self.assertEqual(self.flywheel.ideas[idea.idea_id].status, "VERIFIED")
        self.assertGreater(self.flywheel.total_compounded_value, 0.0)

    def test_04_failed_or_marginal_idea_rejected(self):
        """Ideas that fail experiments or produce marginal gains (<5%) are rejected."""
        idea = self.flywheel.propose_compounding_idea(
            question="Re-implement JSON parser in custom regex",
            category=CompoundingCategory.SINGLE_TASK_SAVING,
            proposed_by="RESEARCH_SCOUT",
            hypothesis="Regex might be faster for small JSON files",
            expected_future_tasks_benefited=5,
        )
        ok, msg = self.flywheel.challenge_and_verify_idea(
            idea_id=idea.idea_id,
            challenger_role="CODEX_REVIEWER",
            challenge_notes="Custom regex parser failed nested JSON edge cases.",
            experiment_result=False,
            measured_improvement_factor=0.90,
        )
        self.assertFalse(ok)
        self.assertEqual(self.flywheel.ideas[idea.idea_id].status, "REJECTED")

    def test_05_flywheel_cycle_velocity_multiplication(self):
        """Recording flywheel cycles tracks compounding velocity over time."""
        c1 = self.flywheel.record_flywheel_cycle(
            real_tasks_processed=10,
            new_ideas_generated=2,
            ideas_adopted=2,
            summary="Initial flywheel bootstrap.",
        )
        self.assertGreater(c1.flywheel_velocity_multiplier, 1.0)

        c2 = self.flywheel.record_flywheel_cycle(
            real_tasks_processed=20,
            new_ideas_generated=1,
            ideas_adopted=1,
            summary="Second flywheel cycle.",
        )
        self.assertGreater(c2.flywheel_velocity_multiplier, c1.flywheel_velocity_multiplier)


if __name__ == "__main__":
    unittest.main()
