"""
Deterministic Unit Tests for Revenue-First Content OS Phase 0
Verifies Opportunity Evaluator, Template Engine, and Programmatic Data Card Renderer.
"""

import os
import sys
import unittest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from opportunity_evaluator import (
    ContentOpportunityEvaluator, OpportunityDimensions, EvidenceEntry, EvidenceType
)
from template_engine import ShortFormTemplateEngine
from lane4_data_renderer import Lane4DataCardRenderer


class TestContentOSPhase0(unittest.TestCase):
    def setUp(self):
        self.evaluator = ContentOpportunityEvaluator()
        self.template_engine = ShortFormTemplateEngine()
        self.card_renderer = Lane4DataCardRenderer()
        self.test_output_dir = os.path.join(os.path.dirname(__file__), "test_output")

    def test_opportunity_evaluator_ready_candidate(self):
        """A high-opportunity, high-automation, low-risk topic passes threshold (>= 70)"""
        dims = OpportunityDimensions(
            trend_velocity=9.0,
            audience_size=8.0,
            monetization_potential=8.5,
            competition=3.0,
            content_half_life=8.0,
            production_cost=0.5,    # Near-zero cost
            production_time=1.0,    # Very fast
            automation_fit=9.5,
            platform_fit=9.0,
            channel_fit=9.0,
            reuse_across_platforms=9.0,
            originality=8.0,
            policy_risk=0.5         # Very safe
        )
        evidence = [
            EvidenceEntry("trend_velocity", 9.0, EvidenceType.OBSERVED_DATA, "Google Trends 48h spike"),
            EvidenceEntry("monetization_potential", 8.5, EvidenceType.ESTIMATE, "SaaS affiliate program 30% recurring"),
            EvidenceEntry("policy_risk", 0.5, EvidenceType.INFERENCE, "100% original educational screen tutorial")
        ]

        result = self.evaluator.evaluate(
            topic_title="Top 3 Open Source AI Dev Tools",
            lane_id="LANE-1-AI-TOOLS",
            dims=dims,
            evidence=evidence
        )
        self.assertTrue(result.is_production_ready)
        self.assertGreaterEqual(result.revenue_opportunity_score, 70.0)
        self.assertIn("READY: YES", result.summary())

    def test_opportunity_evaluator_policy_risk_penalty(self):
        """High policy or copyright risk must heavily penalize the score below threshold"""
        dims = OpportunityDimensions(
            trend_velocity=9.5,
            audience_size=9.5,
            monetization_potential=7.0,
            competition=4.0,
            content_half_life=2.0,
            production_cost=1.0,
            production_time=2.0,
            automation_fit=8.0,
            platform_fit=8.0,
            channel_fit=5.0,
            reuse_across_platforms=5.0,
            originality=2.0,
            policy_risk=8.5         # Severe copyright / guideline risk
        )
        result = self.evaluator.evaluate(
            topic_title="Re-uploading Viral Movie Clips with AI Voice",
            lane_id="LANE-UNKNOWN",
            dims=dims
        )
        self.assertFalse(result.is_production_ready)
        self.assertLess(result.revenue_opportunity_score, 70.0)
        self.assertIn("READY: NO (PARKED)", result.summary())

    def test_template_engine_script_phases(self):
        """Script generator produces structured 4-phase short-form content package"""
        pkg = self.template_engine.generate_short_package(
            video_id="VID-000001",
            lane_id="LANE-1-AI-TOOLS",
            channel_name="Workflow Pulse",
            title="Stop Transcribing Meetings Manually",
            hook_text="You're wasting 3 hours a week if you still transcribe meetings by hand.",
            problem_text="Most teams manually type action items and miss critical project decisions.",
            solution_points=[
                "First, install the local whisper automation.",
                "Second, pipe the audio directly to your summary template.",
                "Third, auto-export the action items straight into markdown."
            ],
            cta_text="Grab the free workflow template in the bio and start saving time.",
            tags=["productivity", "aitools", "workflow", "developer"],
            affiliate_links=["https://example.com/tool1", "https://example.com/tool2"]
        )
        self.assertEqual(len(pkg.script_phases), 4)
        self.assertEqual(pkg.script_phases[0].phase_name, "Hook")
        self.assertEqual(pkg.script_phases[3].phase_name, "Call To Action")
        self.assertEqual(pkg.asset_manifest.aspect_ratio, "9:16")
        self.assertLessEqual(pkg.asset_manifest.target_duration_sec, 60)
        formatted = pkg.formatted_script()
        self.assertIn("[HOOK | 0-3s]", formatted)
        self.assertIn("[CALL TO ACTION | 45-60s]", formatted)

    def test_lane4_data_card_rendering(self):
        """Lane 4 programmatic renderer creates a 1080x1920 vertical ranking image"""
        items = [
            ("Japan", 98.0, "$11.2T (260%)"),
            ("Greece", 75.0, "$410B (170%)"),
            ("Italy", 68.0, "$3.1T (145%)"),
            ("United States", 60.0, "$34.5T (123%)"),
            ("France", 52.0, "$3.3T (111%)")
        ]
        out_file = os.path.join(self.test_output_dir, "test_ranking_card.png")
        rendered_path = self.card_renderer.render_ranking_card(
            title="Top Indebted Nations",
            subtitle="Debt-to-GDP Ratio 2026 Ranking",
            items=items,
            source_attribution="IMF World Economic Outlook 2026",
            output_path=out_file
        )

        self.assertTrue(os.path.exists(rendered_path))
        with Image.open(rendered_path) as im:
            self.assertEqual(im.size, (1080, 1920))
            self.assertEqual(im.mode, "RGB")

        # Clean up test output
        if os.path.exists(rendered_path):
            os.remove(rendered_path)
        if os.path.exists(self.test_output_dir):
            os.rmdir(self.test_output_dir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
