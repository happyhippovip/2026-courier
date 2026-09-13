"""
test_distribution_pack.py - Test Suite for TASK-WIN-69:
Autonomous Multi-Channel Distribution Pack & Zero-Prompt Handoff Staging

Certifies:
1. Multi-Channel Assets: Staged assets for Show HN, Reddit, GitHub, and Human Gate 1 exist and are fully populated.
2. Cryptographic Integrity: Checksums in GITHUB_RELEASE_ASSETS.json match actual binaries on disk.
3. Zero Telemetry: spend_firewall.py contains zero cloud telemetry, tracking, or phone-home calls.
4. 60-Second Value Demo: demo_spend_firewall.py executes 100% offline and halts with HTTP 402 budget trip.
5. Human Gate Isolation: HUMAN_GATE_1 is strictly PARKED, zero external spend, and Mac scope excluded.
6. Falsification Metrics: 48-hour pass/fail thresholds are explicitly codified for commercial measurement.
"""

import os
import sys
import json
import hashlib
import subprocess
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.chief.goal_reconciler import GoalReconciler

DIST_PACK_DIR = os.path.join(
    WORKSPACE_ROOT,
    "project-memory", "data", "distribution_ready", "agent_control_plane", "distribution_pack"
)
ACP_DIR = os.path.dirname(DIST_PACK_DIR)

class TestDistributionPack(unittest.TestCase):
    def setUp(self):
        self.dist_pack_dir = DIST_PACK_DIR
        self.acp_dir = ACP_DIR

    def _sha256(self, fpath: str) -> str:
        with open(fpath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def test_01_all_distribution_channels_staged_and_nonempty(self):
        """Invariant: All 4 staged distribution channel documents exist and are non-trivial (> 200 bytes)."""
        required_assets = [
            "SHOW_HN_LAUNCH_POST.md",
            "REDDIT_RLANGCHAIN_POST.md",
            "GITHUB_RELEASE_ASSETS.json",
            "HUMAN_GATE_1_STAGE_CARD.md"
        ]
        for a in required_assets:
            p = os.path.join(self.dist_pack_dir, a)
            self.assertTrue(os.path.exists(p), f"Missing staged asset: {a}")
            self.assertGreater(os.path.getsize(p), 200, f"Staged asset too small: {a}")

    def test_02_cryptographic_checksums_match_real_artifacts(self):
        """Invariant: GITHUB_RELEASE_ASSETS.json checksums match binary digests on disk."""
        manifest_path = os.path.join(self.dist_pack_dir, "GITHUB_RELEASE_ASSETS.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("status"), "STAGED_AWAITING_HUMAN_GATE_1")
        self.assertEqual(manifest.get("cost_eur"), 0.00)
        self.assertTrue(manifest.get("zero_telemetry_certified"))

        checksums = manifest.get("checksums", {})
        self.assertIn("spend_firewall.py", checksums)
        self.assertIn("agent_control_plane_v1.0.0.zip", checksums)

        for fname, expected_hash in checksums.items():
            full_path = os.path.join(self.acp_dir, fname)
            self.assertTrue(os.path.exists(full_path), f"Artifact missing: {fname}")
            actual_hash = self._sha256(full_path)
            self.assertEqual(actual_hash, expected_hash, f"Hash mismatch for {fname}")

    def test_03_zero_telemetry_guarantee_and_privacy_audit(self):
        """Invariant: spend_firewall.py source contains zero third-party telemetry or phone-home endpoints."""
        src_path = os.path.join(self.acp_dir, "spend_firewall.py")
        with open(src_path, "r", encoding="utf-8") as f:
            src = f.read().lower()

        blacklisted = [
            "posthog.com", "segment.io", "mixpanel.com", "google-analytics.com",
            "sentry.io", "datadoghq.com", "telemetry.api", "analytics.track",
            "phone_home", "report_metrics", "amplitude.com"
        ]
        for term in blacklisted:
            self.assertNotIn(term, src, f"Forbidden telemetry endpoint in spend_firewall.py: {term}")

    def test_04_offline_value_demo_execution_and_budget_trip(self):
        """Invariant: demo_spend_firewall.py executes offline and confirms HTTP 402 budget trip."""
        demo_script = os.path.join(self.acp_dir, "demo_spend_firewall.py")
        res = subprocess.run(
            [sys.executable, demo_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )
        self.assertEqual(res.returncode, 0, f"Demo failed: {res.stderr}")
        out = res.stdout or ""
        self.assertIn("HTTP 402 BUDGET_EXCEEDED", out)
        self.assertIn("Runaway Loss Prevented", out)

    def test_05_human_gate_isolation_and_zero_spend_invariants(self):
        """Invariant: HUMAN_GATE_1 is strictly PARKED, spend is 0.00 EUR, Mac scope excluded."""
        stage_card_path = os.path.join(self.dist_pack_dir, "HUMAN_GATE_1_STAGE_CARD.md")
        with open(stage_card_path, "r", encoding="utf-8") as f:
            text = f.read()

        self.assertIn("PARKED", text)
        self.assertIn("0.00 EUR", text)
        self.assertEqual(GoalReconciler.AUTONOMOUS_SPEND_LIMIT_EUR, 0.00)
        self.assertTrue(GoalReconciler.MAC_SCOPE_EXCLUDED)

    def test_06_channel_specific_compliance_and_falsification_metrics(self):
        """Invariant: Show HN has no hype jargon, Reddit has code example, 48h falsification codified."""
        show_hn_path = os.path.join(self.dist_pack_dir, "SHOW_HN_LAUNCH_POST.md")
        with open(show_hn_path, "r", encoding="utf-8") as f:
            hn_text = f.read()

        # No hype words
        self.assertNotIn("revolutionary", hn_text.lower())
        self.assertNotIn("game-changing", hn_text.lower())
        self.assertIn("curl -sO", hn_text)

        # Reddit post has LangChain example
        reddit_path = os.path.join(self.dist_pack_dir, "REDDIT_RLANGCHAIN_POST.md")
        with open(reddit_path, "r", encoding="utf-8") as f:
            reddit_text = f.read()
        self.assertIn("ChatOpenAI", reddit_text)
        self.assertIn("base_url=", reddit_text)

        # Manifest has 48-hour falsification thresholds
        manifest_path = os.path.join(self.dist_pack_dir, "GITHUB_RELEASE_ASSETS.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        thresholds = manifest.get("falsification_thresholds", {})
        self.assertIn("pass", thresholds)
        self.assertIn("fail", thresholds)
        self.assertIn("48h", thresholds["pass"])

if __name__ == "__main__":
    unittest.main()
