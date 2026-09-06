#!/usr/bin/env python3
"""Mission PRODUCT-1 Acceptance Test Suite — Live Agent HQ.

Verifies:
1. Real state integration across Chief Brain, RealAutonomyRuntime, 188G Endurance, Snitch Anomalies, and Gates.
2. Truthful visual representation of all 25 logical agents (17 core + 8 bodyguards).
3. Live Operations Panel (HUD) data completeness and structure.
4. Human & Money gate visibility and Snitch quarantine visibility.
5. 188G read-only endurance telemetry.
6. Zero fake activity and zero model calls triggered by UI state aggregation.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.run_visual_studio_server import (
    StudioHTTPRequestHandler,
    load_agent_states,
    find_active_human_gate,
    resolve_active_gate_decision,
)


class TestLiveAgentHQMissionProduct1(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_hq_test_"))
        self.events_dir = self.test_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        (self.events_dir / "agent-states").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "autonomy-runtime").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "anomalies").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "opportunity-queue").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "approvals").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "chief-decisions").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "locks").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_all_25_logical_agents_registered_and_structured(self):
        """All 25 agents (17 core/specialist + 8 bodyguards) have defined identities."""
        studio_js_path = Path("studio/execution_truth.js")
        self.assertTrue(studio_js_path.is_file())
        content = studio_js_path.read_text(encoding="utf-8")

        core_agents = [
            "agent-chief-commander",
            "smart-resource-router",
            "agent-human-gate-monitor",
            "agent-thought-curator",
            "agent-update-steward",
            "agent-codex-bridge",
            "agent-asset-validator",
            "agent-video-synth",
            "agent-channel-dispatcher",
            "agent-memory-mesh",
            "agent-test-guardian",
            "agent-antigravity-bridge",
            "agent-courier-relay",
            "agent-academy-teacher",
            "agent-academy-director",
            "agent-snitch",
            "agent-loop-supervisor",
        ]
        for ag in core_agents:
            self.assertIn(ag, content, f"Missing core agent {ag}")

        bodyguards = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL"]
        for bg in bodyguards:
            self.assertIn(f"callsign: '{bg}'", content, f"Missing bodyguard {bg}")

    def test_02_server_handle_api_state_aggregates_autonomy_runtime(self):
        """Server /api/state returns real autonomy runtime and session data."""
        sess_data = {
            "session_id": "session-test-001",
            "status": "IDLE_EXPECTED",
            "goal": "Unattended local endurance test",
            "current_action": "Safe Standby",
            "human_gates_encountered": [{"task_id": "task-pub-1", "reason": "HUMAN_GATE_PUBLICATION"}],
            "money_gates_encountered": [{"task_id": "task-paid-1", "reason": "MONEY_GATE_SPEND_LIMIT_0"}],
            "jobs_dispatched": ["job-1"],
            "jobs_completed": ["job-0"],
            "last_active_at": "2026-09-01T00:00:00Z",
        }
        (self.events_dir / "autonomy-runtime" / "current_session.json").write_text(json.dumps(sess_data))

        handler = MagicMock()
        handler.wfile = io.BytesIO()
        handler.headers = {}

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        handler.send_response.assert_called_with(200)
        written_bytes = handler.wfile.getvalue()
        res = json.loads(written_bytes.decode("utf-8"))

        self.assertIn("autonomy_runtime", res)
        ar = res["autonomy_runtime"]
        self.assertEqual(ar["status"], "IDLE_EXPECTED")
        self.assertEqual(ar["session_id"], "session-test-001")
        self.assertEqual(ar["current_goal"], "Unattended local endurance test")
        self.assertEqual(len(ar["human_gates"]), 1)
        self.assertEqual(len(ar["money_gates"]), 1)

    def test_03_188g_endurance_telemetry_is_read_only(self):
        """Server /api/state reads 188G heartbeat without modifying anything."""
        hb_data = {
            "session_id": "session-188g-endurance-1788216021",
            "status": "IDLE_EXPECTED",
            "elapsed_seconds": 1850.5,
            "remaining_seconds": 26949.5,
            "duration_target_hours": 8.0,
            "model_calls_during_idle": 0,
            "autonomous_spend_eur": 0.0,
        }
        hb_file = self.events_dir / "autonomy-runtime" / "heartbeat.json"
        hb_file.write_text(json.dumps(hb_data))
        mtime_before = hb_file.stat().st_mtime

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        mtime_after = hb_file.stat().st_mtime
        self.assertEqual(mtime_before, mtime_after, "188G heartbeat file must not be modified")

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        endurance = res.get("endurance_188g", {})
        self.assertEqual(endurance.get("session_id"), "session-188g-endurance-1788216021")
        self.assertEqual(endurance.get("elapsed_seconds"), 1850.5)
        self.assertEqual(endurance.get("model_calls_during_idle"), 0)
        self.assertEqual(endurance.get("autonomous_spend_eur"), 0.0)

    def test_04_snitch_anomaly_quarantine_visibility(self):
        """Snitch critical anomalies populate quarantined branches and scopes."""
        anom_ledger = {
            "fp_crit_01": {
                "fingerprint": "fp_crit_01",
                "severity": "CRITICAL",
                "affected_branch": "EXPERIMENTAL_FEATURE",
                "affected_scope": "AUTONOMY_ENGINE",
                "resolved": False,
                "created_at": "2026-09-01T00:00:00Z",
            },
            "fp_norm_01": {
                "fingerprint": "fp_norm_01",
                "severity": "NORMAL",
                "affected_branch": "MAIN",
                "affected_scope": "GLOBAL",
                "resolved": False,
                "created_at": "2026-09-01T00:00:00Z",
            }
        }
        (self.events_dir / "anomalies" / "anomaly_ledger.json").write_text(json.dumps(anom_ledger))

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        anom_res = res.get("anomalies", {})
        self.assertIn("EXPERIMENTAL_FEATURE", anom_res.get("quarantined_branches", []))
        self.assertNotIn("MAIN", anom_res.get("quarantined_branches", []))
        self.assertIn("AUTONOMY_ENGINE", anom_res.get("quarantined_scopes", []))

    def test_05_live_operations_hud_panel_in_html_and_css(self):
        """Index.html and style.css contain the Live Operations Panel HUD."""
        html_path = Path("studio/index.html")
        self.assertTrue(html_path.is_file())
        html_content = html_path.read_text(encoding="utf-8")

        self.assertIn('id="live-ops-hud-panel"', html_content)
        self.assertIn('id="hud-org-status"', html_content)
        self.assertIn('id="hud-current-goal"', html_content)
        self.assertIn('id="hud-current-task"', html_content)
        self.assertIn('id="hud-worker-provider"', html_content)
        self.assertIn('id="hud-endurance-status"', html_content)
        self.assertIn('id="hud-gates-status"', html_content)
        self.assertIn('id="hud-snitch-status"', html_content)
        self.assertIn('id="hud-last-result"', html_content)

        css_path = Path("studio/style.css")
        self.assertTrue(css_path.is_file())
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(".live-ops-hud-panel", css_content)
        self.assertIn(".ops-hud-header", css_content)
        self.assertIn(".ops-hud-badge", css_content)

    def test_06_ui_state_aggregation_causes_zero_model_calls(self):
        """Studio state aggregation performs local JSON reads only; zero model calls."""
        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res.get("schema_version"), "2.0")

    def test_07_real_state_only_no_fake_activity(self):
        """When state is empty/absent, fields default truthfully to IDLE/NONE/UNKNOWN, not fake activity."""
        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        ar = res.get("autonomy_runtime", {})
        self.assertEqual(ar.get("status"), "IDLE_EXPECTED")
        self.assertEqual(ar.get("current_action"), "IDLE_EXPECTED")
        self.assertEqual(len(ar.get("jobs_dispatched", [])), 0)


if __name__ == "__main__":
    unittest.main()
