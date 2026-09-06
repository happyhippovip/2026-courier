#!/usr/bin/env python3
"""Targeted unit tests for Mission 124 YouTube Client Dependencies & Read-Only Canary."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.creator_input_sources import (
    discover_capabilities,
    normalize_youtube_evidence,
    run_youtube_read_only_canary,
    youtube_client_dependencies_available,
)


class TestYouTubeReadOnlyCanaryMission124(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_m124_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dependency_imports(self):
        self.assertTrue(youtube_client_dependencies_available())
        import google.auth
        import google.oauth2.credentials
        import googleapiclient.discovery
        import google_auth_oauthlib.flow

        self.assertIsNotNone(googleapiclient.discovery.build)

    def test_discover_capabilities_with_dependencies(self):
        caps = {item.source: item for item in discover_capabilities()}
        youtube_cap = caps["YOUTUBE"]
        self.assertTrue(youtube_cap.implementation_found)
        self.assertNotEqual(youtube_cap.auth_state, "LOCAL_CLIENT_DEPENDENCIES_MISSING")
        self.assertEqual(youtube_cap.analytics_capability, "NOT_AUTHORIZED")
        self.assertEqual(youtube_cap.write_capability, "HUMAN_GATE")

    def test_read_only_canary_missing_token(self):
        res = run_youtube_read_only_canary(self.test_dir, token_reference="non-existent-token")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["auth_state"], "UNVERIFIED_LOCAL_AUTH_INTERFACE")
        self.assertTrue(res["human_gate_required"])
        self.assertEqual(res["human_gate_reason"], "YOUTUBE_AUTH_HUMAN_GATE")

    def test_read_only_canary_mocked_success(self):
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.refresh_token = "mock_refresh"

        mock_yt = MagicMock()
        mock_channels = MagicMock()
        mock_channels.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "UC_TEST_FRUITKI",
                    "snippet": {"title": "FruitKI", "customUrl": "@kifruchtefilme"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU_TEST_FRUITKI"}},
                }
            ]
        }
        mock_playlist_items = MagicMock()
        mock_playlist_items.list.return_value.execute.return_value = {
            "items": [
                {
                    "contentDetails": {"videoId": "VID_123"},
                    "snippet": {"title": "Test Video 1", "publishedAt": "2026-08-28T19:00:00Z"},
                }
            ]
        }
        mock_videos = MagicMock()
        mock_videos.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "VID_123",
                    "snippet": {"title": "Test Video 1", "publishedAt": "2026-08-28T19:00:00Z"},
                    "status": {"privacyStatus": "public"},
                }
            ]
        }

        mock_yt.channels.return_value = mock_channels
        mock_yt.playlistItems.return_value = mock_playlist_items
        mock_yt.videos.return_value = mock_videos

        with patch("google.oauth2.credentials.Credentials.from_authorized_user_file", return_value=mock_creds), \
             patch("googleapiclient.discovery.build", return_value=mock_yt), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("json.loads", return_value={"token_directory": "."}):

            res = run_youtube_read_only_canary(self.test_dir, token_reference="fruitki-test")

            self.assertEqual(res["status"], "PASS")
            self.assertEqual(res["auth_verification"], "SUCCESS")
            self.assertEqual(res["channel_id"], "UC_TEST_FRUITKI")
            self.assertEqual(res["channel_name"], "FruitKI")
            self.assertEqual(res["real_youtube_items"], 1)
            self.assertEqual(res["youtube_analytics_state"], "YOUTUBE_ANALYTICS_NOT_AUTHORIZED")
            self.assertEqual(res["publications"], 0)
            self.assertEqual(res["mutations"], 0)
            self.assertEqual(res["scope_escalations"], 0)
            self.assertEqual(res["money_spent_eur"], 0.0)

    def test_no_secret_leakage_in_normalized_evidence(self):
        ev = normalize_youtube_evidence(
            channel_id="UC_SECRET_TEST",
            video_id="VID_SEC_1",
            title="Secret Free Video",
            publication_status="public",
            published_at="2026-08-28T12:00:00Z",
            retrieved_at="2026-08-31T00:00:00Z",
            source_endpoint="youtube.videos.list",
        )
        serialized = json.dumps(ev)
        for sensitive in ("token", "secret", "client_id", "password", "key", "auth_code"):
            self.assertNotIn(f'"{sensitive}"', serialized)


if __name__ == "__main__":
    unittest.main()
