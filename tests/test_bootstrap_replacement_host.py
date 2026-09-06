#!/usr/bin/env python3
"""Focused Acceptance Test Suite for Replacement Host Bootstrap (Mission Infinite Life).

Verifies:
1. Successful replacement host bootstrap when DR manifest is valid
2. Host takeover and fencing generation increment
3. Rejection and fail-closed behavior when DR manifest is missing or corrupt
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_replacement_host import bootstrap_replacement_host
from scripts.host_survival_engine import HostSurvivalEngine


class TestBootstrapReplacementHost(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="bootstrap_test_"))
        self.survival_dir = self.test_dir / "events" / "host-survival"
        self.survival_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_bootstrap_success_with_valid_dr_manifest(self):
        """Bootstrap succeeds, fences previous host, and increments generation."""
        engine = HostSurvivalEngine(repo_dir=self.test_dir, host_id="primary-node-01")
        manifest = engine.generate_dr_manifest()

        res = bootstrap_replacement_host(new_host_id="replacement-node-02", repo_dir=self.test_dir)

        self.assertEqual(res["bootstrap_verdict"], "SUCCESS")
        self.assertEqual(res["new_host_id"], "replacement-node-02")
        self.assertEqual(res["new_generation"], 2)
        self.assertIn("primary-node-01", res["fenced_hosts"])
        self.assertTrue(len(res["manifest_digest"]) > 0)

    def test_02_bootstrap_fails_closed_when_dr_manifest_missing(self):
        """Bootstrap raises ValueError if DR manifest does not exist."""
        with self.assertRaises(ValueError) as ctx:
            bootstrap_replacement_host(new_host_id="replacement-node-02", repo_dir=self.test_dir)
        self.assertIn("Cannot bootstrap replacement host", str(ctx.exception))

    def test_03_bootstrap_fails_closed_when_dr_manifest_corrupted(self):
        """Bootstrap raises ValueError if DR manifest is corrupt."""
        manifest_file = self.survival_dir / "disaster_recovery_manifest.json"
        manifest_file.write_text("NOT_VALID_JSON", encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            bootstrap_replacement_host(new_host_id="replacement-node-02", repo_dir=self.test_dir)
        self.assertIn("Cannot bootstrap replacement host", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
