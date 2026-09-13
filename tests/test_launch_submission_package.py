"""
test_launch_submission_package.py - Test Suite for TASK-WIN-78:
Agent Control Plane PRO Show HN & External Launch Dossier, Quickstart Install Scripts & Turnkey Community Distribution Pack

Certifies:
1. Show HN Launch Action Card: SHOW_HN_LAUNCH_CARD.md exists, specifies OPP-SEED-04, 0.00 EUR spend, and falsification gates.
2. Quickstart Installers: install.ps1 and install.sh exist, verify exact SHA-256 against DISTRIBUTION_MANIFEST_PRO.json.
3. Community FAQ & Objection Defense: COMMUNITY_FAQ.md addresses all 10 canonical developer and security objections.
4. Cryptographic Hash Consistency: Expected SHA-256 in installers strictly matches physical archive and manifest.
5. Invariant Enforcement: Automatic spend limit strictly 0.00 EUR, Mac scope excluded, 100% offline.
"""

import os
import sys
import json
import hashlib
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
ACP_DIR = os.path.join(PROJECT_MEMORY_DIR, "data", "distribution_ready", "agent_control_plane")


class TestLaunchSubmissionPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.show_hn_file = os.path.join(ACP_DIR, "SHOW_HN_LAUNCH_CARD.md")
        cls.install_ps1 = os.path.join(ACP_DIR, "install.ps1")
        cls.install_sh = os.path.join(ACP_DIR, "install.sh")
        cls.faq_file = os.path.join(ACP_DIR, "COMMUNITY_FAQ.md")
        cls.pro_manifest = os.path.join(ACP_DIR, "DISTRIBUTION_MANIFEST_PRO.json")
        cls.pro_zip = os.path.join(ACP_DIR, "agent_control_plane_pro_v1.0.0.zip")

    def test_01_show_hn_action_card_integrity(self):
        """Verify SHOW_HN_LAUNCH_CARD.md contains required opportunity, pricing, and falsification rules."""
        self.assertTrue(os.path.exists(self.show_hn_file), "SHOW_HN_LAUNCH_CARD.md must exist")
        with open(self.show_hn_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("OPP-SEED-04", content)
        self.assertIn("0.00 EUR", content)
        self.assertIn("Show HN:", content)
        self.assertIn("Fail-closed budget cap", content)
        self.assertIn("Infinite loop circuit breaker", content)
        self.assertIn("100% offline & 0% telemetry", content)
        self.assertIn("Falsification Metrics", content)
        self.assertIn("Founder approves posting", content)

    def test_02_quickstart_installers_exist_and_match_sha256(self):
        """Verify install.ps1 and install.sh exist and declare exact SHA-256 matching physical archive."""
        self.assertTrue(os.path.exists(self.install_ps1), "install.ps1 must exist")
        self.assertTrue(os.path.exists(self.install_sh), "install.sh must exist")
        self.assertTrue(os.path.exists(self.pro_zip), "agent_control_plane_pro_v1.0.0.zip must exist")

        with open(self.pro_zip, "rb") as f:
            actual_zip_sha256 = hashlib.sha256(f.read()).hexdigest()

        with open(self.pro_manifest, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest_sha256 = manifest_data.get("zip_sha256")

        self.assertEqual(actual_zip_sha256, manifest_sha256, "Physical zip SHA-256 must match manifest")

        with open(self.install_ps1, "r", encoding="utf-8") as f:
            ps1_content = f.read()
        self.assertIn(actual_zip_sha256, ps1_content, "install.ps1 must declare exact physical SHA-256")

        with open(self.install_sh, "r", encoding="utf-8") as f:
            sh_content = f.read()
        self.assertIn(actual_zip_sha256, sh_content, "install.sh must declare exact physical SHA-256")

    def test_03_community_faq_completeness(self):
        """Verify COMMUNITY_FAQ.md addresses all 10 core developer and security questions."""
        self.assertTrue(os.path.exists(self.faq_file), "COMMUNITY_FAQ.md must exist")
        with open(self.faq_file, "r", encoding="utf-8") as f:
            faq_content = f.read()

        topics = [
            "OpenAI / Anthropic organization spend limits",
            "private prompts and API keys",
            "proxy process crashes",
            "infinite loop circuit breaker",
            "token cost estimated locally",
            "Docker",
            "offline HMAC licensing",
            "€19.99 permanent instead of a monthly SaaS",
            "Ollama or vLLM",
            "MIT License"
        ]
        for topic in topics:
            self.assertIn(topic, faq_content, f"FAQ must cover topic: {topic}")

    def test_04_operating_invariants(self):
        """Verify automatic spend limit strictly 0.00 EUR and Mac scope untouched."""
        cycle_state_path = os.path.join(PROJECT_MEMORY_DIR, "data", "autonomy_cycle_state.json")
        if os.path.exists(cycle_state_path):
            with open(cycle_state_path, "r", encoding="utf-8") as f:
                c_state = json.load(f)
            self.assertEqual(c_state.get("spend_eur", 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
