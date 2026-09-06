#!/usr/bin/env python3
"""Test suite for ContentTransformationEngine."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.package_content_transformation_service import ContentTransformationEngine


class TestContentTransformationEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="content_trans_test_"))
        self.engine = ContentTransformationEngine(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_transform_raw_notes_into_three_marketing_assets(self):
        """Transforms input notes into LinkedIn post, carousel deck, and newsletter teaser."""
        notes = "Raw technical discussion on crash-proof worker recovery and POSIX file locks."
        res = self.engine.transform_raw_notes(notes, topic_title="Agent Crash Safety")

        self.assertIn("package_id", res)
        self.assertEqual(res["capital_spent_eur"], 0.0)

        # Verify all 3 asset files exist
        post_path = self.test_dir / res["assets"]["linkedin_post"]
        carousel_path = self.test_dir / res["assets"]["carousel_deck"]
        newsletter_path = self.test_dir / res["assets"]["newsletter_teaser"]

        self.assertTrue(post_path.exists())
        self.assertTrue(carousel_path.exists())
        self.assertTrue(newsletter_path.exists())

        post_text = post_path.read_text(encoding="utf-8")
        self.assertIn("LinkedIn / X Technical Founder Post", post_text)
        self.assertIn("POSIX Lease Locking", post_text)


if __name__ == "__main__":
    unittest.main()
