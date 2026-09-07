import unittest
import tempfile
import time
from pathlib import Path
from typing import Any

from scripts.founder_concierge_dossier import (
    FounderChaosParser,
    FounderConciergePipeline,
    FounderExecutionDossier,
    OutcomeMetrics,
    GoalItem,
    DecisionItem,
    AssumptionItem,
    OpenQuestionItem,
    ActionableTaskItem,
    DeliverableItem
)
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher, TaskEnvelope
from scripts.courier_founder_mode import FounderModeMVP

class TestFounderChaosParser(unittest.TestCase):
    def setUp(self):
        self.parser = FounderChaosParser()

    def test_parse_structured_sections(self):
        raw_chaos = """
        Goal: Build automated concierge that turns chaotic founder thoughts into structured execution dossiers
        Outcome: Founders save 10 hours a week on project management
        Decision: Use lightweight Python dataclasses instead of complex ORM
        Assumption: Founders prefer instant markdown and JSON exports
        Question: How do we measure manual rework reduction?
        TODO: Implement chaos parser with robust regex patterns
        Task: Add outcome metrics calculator for dossier generation
        Deliverable: scripts/founder_concierge_dossier.py
        Priority: P0: Dossier generation engine
        """
        parsed = self.parser.parse(raw_chaos)
        self.assertGreaterEqual(len(parsed["goals"]), 1)
        self.assertEqual(parsed["goals"][0].title, "Build automated concierge that turns chaotic founder thoughts into structured execution dossiers")
        
        self.assertGreaterEqual(len(parsed["decisions"]), 1)
        self.assertIn("lightweight Python dataclasses", parsed["decisions"][0].decision)
        self.assertIn("complex ORM", parsed["decisions"][0].alternatives_considered)
        
        self.assertGreaterEqual(len(parsed["assumptions"]), 1)
        self.assertIn("Founders prefer instant", parsed["assumptions"][0].statement)
        
        self.assertGreaterEqual(len(parsed["open_questions"]), 1)
        self.assertIn("manual rework reduction", parsed["open_questions"][0].question)
        
        self.assertGreaterEqual(len(parsed["tasks"]), 2)
        self.assertGreaterEqual(len(parsed["deliverables"]), 1)
        self.assertGreaterEqual(len(parsed["priorities"]), 1)

    def test_parse_messy_unstructured_braindump(self):
        messy_dump = """
        Hey team, quick brain dump from my meeting with advisors:
        We need to get Courier Founder Mode to a real usable product ASAP.
        We decided to focus on zero-human-coordination loops rather than complex UI dashboards.
        Assume that local tests are sufficient for immediate verification before cloud runs.
        What if the worker gets rate limited or fails mid-mission?
        - [ ] Create automated repair mechanism for transient network timeouts
        - [ ] Add dossier export in clean markdown format
        Need a deliverable spec for the founder execution report.
        """
        parsed = self.parser.parse(messy_dump)
        self.assertGreaterEqual(len(parsed["goals"]), 1)
        self.assertGreaterEqual(len(parsed["decisions"]), 1)
        self.assertGreaterEqual(len(parsed["assumptions"]), 1)
        self.assertGreaterEqual(len(parsed["open_questions"]), 1)
        self.assertGreaterEqual(len(parsed["tasks"]), 2)

    def test_parse_fallback_handling(self):
        minimal_text = "Quick note: fix login timeout on the API backend."
        parsed = self.parser.parse(minimal_text)
        self.assertEqual(len(parsed["goals"]), 1)
        self.assertGreaterEqual(len(parsed["tasks"]), 1)
        self.assertGreaterEqual(len(parsed["deliverables"]), 1)
        self.assertGreaterEqual(len(parsed["priorities"]), 1)

class TestFounderConciergePipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_dir = Path(self.temp_dir.name)
        self.pipeline = FounderConciergePipeline(self.workspace_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_process_chaos_and_outcome_metrics(self):
        raw_chaos = """
        Goal: Build Founder Concierge Chaos-to-Execution Dossier pipeline
        Decision: Integrate directly with Courier MultiChatGoalIntake
        Assumption: Dispatcher processes missions without manual human gates
        Question: Should we support voice audio transcripts as input?
        TODO: Write unit tests for pipeline parsing and serialization
        Deliverable: tests/test_founder_concierge_dossier.py
        """
        dossier = self.pipeline.process_chaos(
            raw_chaos=raw_chaos,
            source="user_chat",
            title="Founder Concierge Pipeline Rollout"
        )

        self.assertIsInstance(dossier, FounderExecutionDossier)
        self.assertEqual(dossier.title, "Founder Concierge Pipeline Rollout")
        self.assertEqual(dossier.source, "user_chat")
        self.assertTrue(dossier.dossier_id.startswith("DOSSIER-"))
        
        # Verify outcome metrics
        metrics = dossier.outcome_metrics
        self.assertGreater(metrics.time_to_useful_dossier_seconds, 0.0)
        self.assertLessEqual(metrics.manual_rework_score, 0.5)
        self.assertGreaterEqual(metrics.actionable_tasks_count, 1)
        self.assertGreaterEqual(metrics.unresolved_ambiguities_count, 1)
        self.assertEqual(metrics.verification_outcome_score, 1.0)
        
        # Verify markdown content generated
        self.assertIn("# 📋 Founder Execution Dossier: Founder Concierge Pipeline Rollout", dossier.markdown_content)
        self.assertIn("## 🎯 Structured Strategic Goals", dossier.markdown_content)
        self.assertIn("## ⚖️ Key Decision Log", dossier.markdown_content)
        self.assertIn("## ⚡ Concrete Actionable Tasks", dossier.markdown_content)
        self.assertIn("## 📊 Outcome & Value Evidence Metrics", dossier.markdown_content)

    def test_save_load_and_export_dossier(self):
        raw_chaos = """
        Goal: Launch autonomous founder copilot
        Decision: Ship MVP today instead of next week
        TODO: Verify test suite runs cleanly
        """
        dossier = self.pipeline.process_chaos(raw_chaos, title="MVP Launch")
        
        # Save dossier
        json_path = self.pipeline.save_dossier(dossier)
        self.assertTrue(json_path.exists())
        
        # Check manifest
        manifest_path = self.workspace_dir / "events" / "founder-dossiers" / "dossier_manifest.json"
        self.assertTrue(manifest_path.exists())
        
        # Load dossier
        loaded = self.pipeline.load_dossier(dossier.dossier_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.dossier_id, dossier.dossier_id)
        self.assertEqual(loaded.title, "MVP Launch")
        self.assertEqual(len(loaded.goals), len(dossier.goals))
        self.assertEqual(len(loaded.tasks), len(dossier.tasks))
        
        # Export markdown
        export_file = self.workspace_dir / "exports" / "dossier_export.md"
        content = self.pipeline.export_markdown(dossier, export_file)
        self.assertTrue(export_file.exists())
        self.assertTrue(dossier.outcome_metrics.dossier_exported)
        self.assertIn("MVP Launch", content)

    def test_feed_to_courier_founder_mode(self):
        class MockDispatcher(CourierSafetyDispatcher):
            def __init__(self, workspace_dir):
                super().__init__(workspace_dir)

        dispatcher = MockDispatcher(self.workspace_dir)
        founder_mvp = FounderModeMVP(self.workspace_dir, dispatcher)
        
        raw_chaos = """
        Goal: Deliver verified founder value with automated testing
        TODO: Run unit tests for validation
        """
        dossier = self.pipeline.process_chaos(raw_chaos)
        goal_ids = self.pipeline.feed_to_courier_founder_mode(dossier, founder_mvp)
        
        self.assertGreaterEqual(len(goal_ids), 1)
        goals = founder_mvp.intake._read_no_lock()
        self.assertEqual(len(goals), len(goal_ids))
        self.assertTrue(goals[0]["source"].startswith("founder_concierge:DOSSIER-"))
        self.assertIn("Deliver verified founder value", goals[0]["goal"])

if __name__ == "__main__":
    unittest.main()
