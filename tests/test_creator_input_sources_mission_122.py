#!/usr/bin/env python3
"""Local no-network tests for Mission 122 creator input sources."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.creator_input_sources import (
    build_research_evidence,
    discover_capabilities,
    ingest_research_evidence,
    normalize_source,
    normalize_youtube_evidence,
    refresh_creator_input_sources,
)


class TestCreatorInputSourcesMission122(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="courier_m122_"))

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_source_normalization_rejects_unknown_source(self):
        self.assertEqual(normalize_source(" youtube "), "YOUTUBE")
        with self.assertRaises(ValueError):
            normalize_source("invented paid connector")

    def test_evidence_hash_and_research_dedupe_are_stable(self):
        evidence = build_research_evidence(
            question="Does the verified canonical scope change the current QC decision?",
            source="https://developers.google.com/youtube/v3/guides/auth/installed-apps",
            source_type="OFFICIAL_PUBLIC_DOCUMENTATION",
            finding="youtube.force-ssl remains documented; no current local production decision changes.",
            confidence="HIGH", production_relevance="NO_CURRENT_PIPELINE_CHANGE",
            information_gain="NO_NEW_INFORMATION", retrieved_at="2026-08-31T00:00:00+00:00",
        )
        first, path = ingest_research_evidence(self.repo, evidence)
        second, same_path = ingest_research_evidence(self.repo, evidence)
        self.assertEqual(first, "NO_NEW_INFORMATION")
        self.assertEqual(second, "NO_NEW_INFORMATION")
        self.assertEqual(path, same_path)
        self.assertEqual(len(list(path.parent.glob("*.json"))), 1)

    def test_analytics_are_never_fabricated_when_auth_is_unverified(self):
        with patch("scripts.creator_input_sources.youtube_client_dependencies_available", return_value=True):
            capabilities = {item.source: item for item in discover_capabilities()}
        self.assertFalse(capabilities["YOUTUBE"].safe_to_use_now)
        self.assertEqual(capabilities["YOUTUBE"].analytics_capability, "NOT_AUTHORIZED")
        self.assertFalse(capabilities["TIKTOK"].safe_to_use_now)
        self.assertEqual(capabilities["TIKTOK"].analytics_capability, "NOT_IMPLEMENTED")

    def test_missing_youtube_client_dependencies_fail_closed(self):
        with patch("scripts.creator_input_sources.youtube_client_dependencies_available", return_value=False):
            youtube = {item.source: item for item in discover_capabilities()}["YOUTUBE"]
        self.assertEqual(youtube.auth_state, "LOCAL_CLIENT_DEPENDENCIES_MISSING")
        self.assertEqual(youtube.read_capability, "NOT_AVAILABLE")
        self.assertFalse(youtube.safe_to_use_now)

    def test_youtube_evidence_requires_real_identity_and_never_infers_status(self):
        with self.assertRaises(ValueError):
            normalize_youtube_evidence(
                channel_id="", video_id=None, title=None, publication_status=None,
                published_at=None, retrieved_at="2026-08-31T00:00:00+00:00", source_endpoint="channels.list",
            )
        record = normalize_youtube_evidence(
            channel_id="real-channel-id", video_id=None, title=None, publication_status=None,
            published_at=None, retrieved_at="2026-08-31T00:00:00+00:00", source_endpoint="channels.list",
        )
        self.assertIsNone(record["publication_status"])
        self.assertTrue(record["evidence_hash"])

    def test_refresh_uses_only_durable_research_with_production_impact(self):
        none = refresh_creator_input_sources(self.repo)
        self.assertEqual(none["status"], "NO_NEW_INFORMATION")
        self.assertEqual(none["opportunities"], [])
        evidence = build_research_evidence(
            question="Test", source="official", source_type="OFFICIAL_PUBLIC_DOCUMENTATION",
            finding="Changed requirement", confidence="HIGH",
            production_relevance="CHANGES_PRODUCTION_DECISION", information_gain="NEW_INFORMATION",
        )
        ingest_research_evidence(self.repo, evidence)
        refreshed = refresh_creator_input_sources(self.repo)
        self.assertEqual(refreshed["status"], "EVIDENCE_REQUIRES_CHIEF_REVIEW")
        self.assertEqual(len(refreshed["durable_research_items"]), 1)
        self.assertEqual(refreshed["opportunities"], [])


if __name__ == "__main__":
    unittest.main()
