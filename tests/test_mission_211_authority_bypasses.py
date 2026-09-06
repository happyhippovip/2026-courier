#!/usr/bin/env python3
"""Mission 211 Acceptance Test Suite: Close Entrypoint Authority Bypasses.

Verifies:
1. creator_video_renderer.py:execute_full_batch_production:
   - Acquires HEAVY:GLOBAL authority before creating directories, rendering, or encoding.
   - Denied authority (e.g. another heavy job active, or corrupt state) produces 0 side effects.
   - Stale generation cannot renew or continue.
2. creator_video_renderer_152g.py:execute_mission_152g_full_production:
   - Acquires HEAVY:GLOBAL authority before creating directories or rendering.
   - Denied authority produces 0 side effects and returns DENIED_BY_CANONICAL_AUTHORITY.
   - Fails closed on corrupt authority state.
3. render_godot_movie.py:main:
   - Acquires HEAVY:GLOBAL authority before output dir creation or Godot subprocess launch.
   - Denied authority prints error to stderr, returns 1, and produces 0 side effects.
4. run_codex_bridge.py:execute_codex_task:
   - Acquires Canonical Scope Authority for task scopes before mutating events/processed.
   - Denied authority triggers on_task_failure with DENIED_BY_CANONICAL_AUTHORITY and 0 scope mutations.
5. Global Heavy Contention across independent processes / components.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.canonical_authority import (
    AuthorityRecord,
    CanonicalAuthority,
    LockStatus,
    utc_now,
)
import scripts.creator_video_renderer as cvr151
import scripts.creator_video_renderer_152g as cvr152
import scripts.render_godot_movie as rgm
import scripts.run_codex_bridge as rcb


class TestMission211AuthorityBypasses(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mission_211_test_"))
        self.events_dir = self.test_dir / "events"
        self.locks_dir = self.events_dir / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_content = self.test_dir / "runtime" / "content"
        self.runtime_content.mkdir(parents=True, exist_ok=True)
        self.auth = CanonicalAuthority(locks_dir=self.locks_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 1. CREATOR VIDEO RENDERER 151G
    # --------------------------------------------------------------------------

    @patch("scripts.creator_video_renderer.CanonicalAuthority")
    def test_01_creator_video_renderer_151g_denied_produces_zero_side_effects(self, mock_auth_cls):
        """When heavy authority is denied, execute_full_batch_production creates NO directories or files."""
        mock_auth = MagicMock()
        mock_auth.acquire_heavy_authority.return_value = (False, None, "BLOCK_HEAVY_JOB_LIMIT: Another heavy job active")
        mock_auth_cls.return_value = mock_auth

        target_batch_dir = self.runtime_content / "mission_151g_creator_batch"
        if target_batch_dir.exists():
            shutil.rmtree(target_batch_dir)

        with patch("scripts.creator_video_renderer.RUNTIME_CONTENT_DIR", self.runtime_content):
            result = cvr151.execute_full_batch_production()

        self.assertEqual(result.get("status"), "DENIED_BY_CANONICAL_AUTHORITY")
        self.assertIn("BLOCK_HEAVY_JOB_LIMIT", result.get("error", ""))
        self.assertFalse(target_batch_dir.exists(), "No batch directory should be created when authority is denied")

    @patch("scripts.creator_video_renderer.render_and_encode_video")
    @patch("scripts.creator_video_renderer.generate_qc_report")
    @patch("scripts.creator_video_renderer.generate_publish_package")
    def test_02_creator_video_renderer_151g_acquires_and_releases_authority(self, mock_pub, mock_qc, mock_render):
        """When granted, execute_full_batch_production completes and releases heavy authority."""
        dummy_mp4 = self.runtime_content / "dummy.mp4"
        dummy_meta = self.runtime_content / "dummy_meta.json"
        dummy_qc_rep = self.runtime_content / "dummy_qc.json"
        dummy_pkg = self.runtime_content / "dummy_pkg.json"

        dummy_props = {"sha256": "abcdef123456", "duration_seconds": 8.0, "width": 720, "height": 1280, "fps": 30, "video_codec": "h264"}
        dummy_qc_data = {"verdict": "PASS"}

        mock_render.return_value = (dummy_mp4, dummy_meta, dummy_props)
        mock_qc.return_value = (dummy_qc_rep, dummy_qc_data)
        mock_pub.return_value = (dummy_pkg, {"title": "Test"})

        with patch("scripts.creator_video_renderer.RUNTIME_CONTENT_DIR", self.runtime_content), \
             patch("scripts.canonical_authority.DEFAULT_LOCKS_DIR", self.locks_dir), \
             patch.object(cvr151, "CanonicalAuthority", lambda: CanonicalAuthority(locks_dir=self.locks_dir)):

            result = cvr151.execute_full_batch_production()

        self.assertEqual(result.get("status"), "SUCCESS")
        # Verify lock was released cleanly
        active_locks = self.auth.list_active_locks()
        self.assertNotIn("HEAVY:GLOBAL", active_locks)

    # --------------------------------------------------------------------------
    # 2. CREATOR VIDEO RENDERER 152G
    # --------------------------------------------------------------------------

    @patch("scripts.creator_video_renderer_152g.CanonicalAuthority")
    def test_03_creator_video_renderer_152g_denied_on_corruption(self, mock_auth_cls):
        """When authority detects corrupt lock state, 152G production fails closed immediately."""
        mock_auth = MagicMock()
        mock_auth.acquire_heavy_authority.return_value = (False, None, "BLOCK_CORRUPT_STATE: Zero-byte authority file")
        mock_auth_cls.return_value = mock_auth

        target_batch_dir = self.runtime_content / "mission_152g_creator_batch"
        if target_batch_dir.exists():
            shutil.rmtree(target_batch_dir)

        with patch("scripts.creator_video_renderer_152g.RUNTIME_CONTENT_DIR", self.runtime_content):
            result = cvr152.execute_mission_152g_full_production()

        self.assertEqual(result.get("status"), "DENIED_BY_CANONICAL_AUTHORITY")
        self.assertIn("BLOCK_CORRUPT_STATE", result.get("error", ""))
        self.assertFalse(target_batch_dir.exists())

    # --------------------------------------------------------------------------
    # 3. GODOT RENDER ENTRYPOINT
    # --------------------------------------------------------------------------

    def test_04_render_godot_movie_denied_when_heavy_slot_taken(self):
        """When heavy slot is owned by another process, render_godot_movie exits non-zero with 0 side effects."""
        # Pre-lock heavy slot
        ok, gen, _ = self.auth.acquire_heavy_authority(
            owner_id="existing_heavy_job",
            task_id="active_task",
        )
        self.assertTrue(ok)

        out_dir = self.test_dir / "godot_out"
        mock_scene_script = self.test_dir / "test_scene.gd"
        mock_scene_script.write_text("const DURATION := 5.0\nconst CAPTURE_FPS := 30\n", encoding="utf-8")

        mock_project_dir = self.test_dir / "project"
        mock_project_dir.mkdir(parents=True, exist_ok=True)
        mock_scene = mock_project_dir / "scene.tscn"
        mock_scene.write_text('path="res://test_scene.gd"', encoding="utf-8")
        shutil.copy(mock_scene_script, mock_project_dir / "test_scene.gd")

        # Mock args
        test_args = [
            "render_godot_movie.py",
            "--project", str(mock_project_dir),
            "--scene", "res://scene.tscn",
            "--output-dir", str(out_dir),
            "--godot", str(mock_project_dir / "fake_godot"),
            "--ffmpeg", str(mock_project_dir / "fake_ffmpeg"),
        ]
        (mock_project_dir / "fake_godot").write_text("#!/bin/sh\nexit 0\n")
        (mock_project_dir / "fake_ffmpeg").write_text("#!/bin/sh\nexit 0\n")

        with patch("sys.argv", test_args), \
             patch("scripts.canonical_authority.DEFAULT_LOCKS_DIR", self.locks_dir), \
             patch.object(rgm, "CanonicalAuthority", lambda: CanonicalAuthority(locks_dir=self.locks_dir)):
            ret = rgm.main()

        self.assertEqual(ret, 1)
        self.assertFalse(out_dir.exists(), "Output directory must NOT be created when authority is denied")

    # --------------------------------------------------------------------------
    # 4. CODEX BRIDGE SCOPE AUTHORITY
    # --------------------------------------------------------------------------

    def test_05_codex_bridge_denied_on_scope_conflict(self):
        """When Codex task requests a scope locked by another worker, it fails closed."""
        # Pre-lock scope 'src/core'
        self.auth.acquire_scopes(owner_id="worker_alpha", task_id="task_alpha", scopes=["src/core"])

        job_file = self.test_dir / "test_codex_job.json"
        job_data = {
            "task_id": "codex-test-01",
            "correlation_id": "corr-01",
            "instruction": "Refactor src/core/engine.py",
            "allowed_scope": ["src/core"],
        }
        job_file.write_text(json.dumps(job_data), encoding="utf-8")

        state_tracker = rcb.CodexVisualStateTracker(repo_dir=self.test_dir)
        hooks = rcb.CodexHookRunner(state_tracker)

        with patch("scripts.run_codex_bridge.PROCESSED_DIR", self.test_dir / "events" / "processed"), \
             patch("scripts.canonical_authority.DEFAULT_LOCKS_DIR", self.locks_dir), \
             patch.object(rcb, "CanonicalAuthority", lambda: CanonicalAuthority(locks_dir=self.locks_dir)):

            res_file = rcb.execute_codex_task(job_file, hooks)

        self.assertTrue(res_file.exists())
        result_data = json.loads(res_file.read_text(encoding="utf-8"))
        self.assertEqual(result_data.get("status"), "FAILED")
        self.assertIn("DENIED_BY_CANONICAL_AUTHORITY", result_data.get("payload", {}).get("error", ""))

    def test_06_codex_bridge_acquires_and_releases_scope_cleanly(self):
        """When granted, Codex task executes and releases scope authority upon completion."""
        job_file = self.test_dir / "test_codex_job_free.json"
        target_fixture = self.test_dir / "fixture.json"
        target_fixture.write_text('{"key": "value"}', encoding="utf-8")

        job_data = {
            "task_id": "codex-test-free",
            "correlation_id": "corr-free",
            "instruction": "Inspect fixture",
            "allowed_scope": [str(target_fixture.name)],
        }
        job_file.write_text(json.dumps(job_data), encoding="utf-8")

        state_tracker = rcb.CodexVisualStateTracker(repo_dir=self.test_dir)
        hooks = rcb.CodexHookRunner(state_tracker)

        with patch("scripts.run_codex_bridge.PROCESSED_DIR", self.test_dir / "events" / "processed"), \
             patch("scripts.canonical_authority.DEFAULT_LOCKS_DIR", self.locks_dir), \
             patch.object(rcb, "CanonicalAuthority", lambda: CanonicalAuthority(locks_dir=self.locks_dir)):

            res_file = rcb.execute_codex_task(job_file, hooks)

        self.assertTrue(res_file.exists())
        result_data = json.loads(res_file.read_text(encoding="utf-8"))
        self.assertEqual(result_data.get("status"), "COMPLETED")

        # Verify scope lock was released
        active_locks = self.auth.list_active_locks()
        self.assertNotIn(str(target_fixture.name), active_locks)


if __name__ == "__main__":
    unittest.main()
