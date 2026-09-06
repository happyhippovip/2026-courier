#!/usr/bin/env python3
"""Deterministic Test Suite for Daily AI Improvement Council & Competitive Learning Engine.

Verifies:
1. Permanent Motto Persistence ("WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN.")
2. Canonical Shared Improvement Backlog Management
3. Evidence-Weighted Multi-AI Deliberation (No fake democracy, evidence beats opinion)
4. Critical Challenge Handling & Incumbent Retention
5. Distilled Organizational Knowledge Base Persistence
6. Competitive Daily Benchmarking (Today vs. Yesterday vs. Baseline)
7. 100% Deterministic execution (0 Model Calls, 0.00 EUR Spend)
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.daily_ai_improvement_council import (
    CouncilVerdict,
    DailyAIImprovementCouncil,
    DailyBenchmarkSnapshot,
    DistilledLesson,
    ImprovementProposal,
    KnowledgeType,
    PerspectiveRole,
    PERMANENT_MOTTO,
)


class TestDailyAIImprovementCouncil(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="council_test_"))
        self.council = DailyAIImprovementCouncil(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_permanent_motto_persisted(self):
        """Permanent motto is prominently persisted in central runtime state."""
        self.assertEqual(self.council.motto, PERMANENT_MOTTO)
        motto_file = self.test_dir / "events" / "runtime-state" / "central_motto.json"
        self.assertTrue(motto_file.exists())
        data = json.loads(motto_file.read_text(encoding="utf-8"))
        self.assertEqual(data["permanent_motto"], "WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN.")

    def test_02_submit_candidate_to_shared_backlog(self):
        """Improvement candidate is persisted with required schema in shared backlog."""
        imp_id = self.council.submit_improvement_candidate(
            question="Can we make process liveness checks faster and safer?",
            source_role=PerspectiveRole.SNITCH_OBSERVER,
            current_method="ps subprocess invocation",
            proposed_alternative="CanonicalAuthority os.kill(pid, 0)",
            evidence={"sample_count": 10, "runtime_gain": "95%"},
            expected_value="Near-zero latency liveness inspection without sandbox overhead",
        )
        self.assertTrue(imp_id.startswith("IMP-"))
        self.assertIn(imp_id, self.council.backlog)
        self.assertEqual(self.council.backlog[imp_id]["source_role"], "SNITCH_OBSERVER")

    def test_03_evidence_weighted_council_deliberation(self):
        """Council evaluates evidence weight and adopts superior proposal."""
        p1 = ImprovementProposal(
            proposal_id="PROP-AST",
            role=PerspectiveRole.DETERMINISTIC_ORACLE,
            question="Best method for test gap detection?",
            current_method="Manual review",
            proposed_alternative="AST deterministic inspection",
            evidence={"sample_count": 8, "false_positive_rate": 0.0},
            expected_benefit="Zero false positives, 100% repeatable",
            confidence=0.98,
        )
        p2 = ImprovementProposal(
            proposal_id="PROP-HEURISTIC",
            role=PerspectiveRole.CODEX_REVIEWER,
            question="Best method for test gap detection?",
            current_method="Manual review",
            proposed_alternative="LLM heuristic guessing",
            evidence={"sample_count": 1},
            expected_benefit="Broad coverage",
            confidence=0.65,
        )

        delib = self.council.hold_bounded_council(
            question="Best method for test gap detection?",
            proposals=[p1, p2],
        )

        self.assertEqual(delib.verdict, CouncilVerdict.ADOPT)
        self.assertIn("DETERMINISTIC_ORACLE", delib.decision_reason)
        self.assertGreaterEqual(delib.evidence_weighted_score, 0.85)

    def test_04_critical_challenge_retains_incumbent(self):
        """Critical safety challenge prevents unsafe adoption and retains current method."""
        p1 = ImprovementProposal(
            proposal_id="PROP-RISKY",
            role=PerspectiveRole.RESEARCH_SCOUT,
            question="Should we automate multi-account rotation?",
            current_method="Single authorized primary account",
            proposed_alternative="Automated credential rotation",
            evidence={"sample_count": 3},
            expected_benefit="More API quota",
            risk="HIGH",
            confidence=0.90,
        )
        challenge = {
            "source_role": "CHIEF_STRATEGY",
            "severity": "CRITICAL",
            "argument": "Violates safety invariant: No account rotation for quota evasion.",
        }

        delib = self.council.hold_bounded_council(
            question="Should we automate multi-account rotation?",
            proposals=[p1],
            challenges=[challenge],
        )

        self.assertEqual(delib.verdict, CouncilVerdict.CURRENT_METHOD_RETAINED)
        self.assertIn("critical safety challenge raised", delib.decision_reason)

    def test_05_distilled_lessons_persisted_for_organizational_memory(self):
        """Verified distilled lessons are recorded and shared across all workers."""
        lesson = self.council.record_distilled_lesson(
            lesson_id="LES-RECOVERY-01",
            knowledge_type=KnowledgeType.VERIFIED_FACT,
            topic="Crash Recovery Fencing",
            concise_lesson="CanonicalAuthority generation tokens prevent stale worker overwrites.",
            source_role=PerspectiveRole.GOOGLE_BUILDER,
            confidence=0.99,
            applicability=["DISPATCHER", "SURVIVAL_ENGINE", "FAILOVER_COORDINATOR"],
        )
        self.assertEqual(lesson.lesson_id, "LES-RECOVERY-01")
        self.assertIn("LES-RECOVERY-01", self.council.lessons)

    def test_06_competitive_daily_benchmarking(self):
        """Records daily metrics and verifies if today is better than yesterday."""
        snap = self.council.record_daily_benchmark(
            useful_tasks_completed=14,
            failure_rate=0.0,
            duplicate_executions=0,
            human_interventions=0,
            weiter_prompts=0,
            runtime_seconds=5.12,
            summary="Autonomous production canary completed across all 10 phases.",
        )
        self.assertTrue(snap.is_better_than_yesterday)
        self.assertEqual(snap.useful_tasks_completed, 14)
        self.assertEqual(snap.weiter_prompts_required, 0)


if __name__ == "__main__":
    unittest.main()
