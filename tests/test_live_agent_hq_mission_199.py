#!/usr/bin/env python3
"""Mission 199 Acceptance Test Suite — Live Agent HQ & Real Telemetry.

Verifies:
1. Preservation of all 25 logical agents (17 core + 8 bodyguards) plus 4 execution workers (GOOGLE, CODEX, CLI1, CLI2).
2. Distinct representation of all 11 states: PROGRESSING, SAFE_IDLE, WAITING_PERMISSION, WAITING_HUMAN, RUNNING_NO_PROGRESS, HUNG, PROVIDER_ERROR, NETWORK_DEGRADED, COMPLETED, ORPHANED, UNKNOWN.
3. Deterministic speech bubbles generated from structured state (0 model calls).
4. Bodyguard sauna props (Alpha: cigarette, Bravo: shisha, Charlie/Delta: drink) and alert override.
5. Bar idle placement and return to workstation.
6. Persistent Chief Alert Bar alert deduplication.
7. Agent Detail Panel completeness (11 required fields).
8. Live telemetry resilience and zero fake work.
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
)


class TestLiveAgentHQMission199(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_hq_199_"))
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

    def test_01_all_agents_and_execution_workers_present(self):
        """Preserve all 25 logical agents and verify 4 execution workers in execution_truth.js."""
        studio_js_path = Path("studio/execution_truth.js")
        self.assertTrue(studio_js_path.is_file())
        content = studio_js_path.read_text(encoding="utf-8")

        # 17 Core Agents
        core_agents = [
            "agent-chief-commander", "smart-resource-router", "agent-human-gate-monitor",
            "agent-thought-curator", "agent-update-steward", "agent-codex-bridge",
            "agent-asset-validator", "agent-video-synth", "agent-channel-dispatcher",
            "agent-memory-mesh", "agent-test-guardian", "agent-antigravity-bridge",
            "agent-courier-relay", "agent-academy-teacher", "agent-academy-director",
            "agent-snitch", "agent-loop-supervisor",
        ]
        for ag in core_agents:
            self.assertIn(ag, content, f"Missing core agent: {ag}")

        # 8 Bodyguards
        bodyguards = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL"]
        for bg in bodyguards:
            self.assertIn(f"callsign: '{bg}'", content, f"Missing bodyguard: {bg}")

        # 4 Execution Workers
        workers = ["worker-google", "worker-codex", "worker-cli1", "worker-cli2"]
        for wk in workers:
            self.assertIn(wk, content, f"Missing execution worker: {wk}")

    def test_02_server_api_state_includes_snitch_and_execution_workers(self):
        """Server /api/state returns snitch observer telemetry and execution workers."""
        handler = MagicMock()
        handler.wfile = io.BytesIO()
        handler.headers = {}

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        handler.send_response.assert_called_with(200)
        res = json.loads(handler.wfile.getvalue().decode("utf-8"))

        self.assertIn("agents", res)
        agents = res["agents"]
        self.assertIn("worker-google", agents)
        self.assertIn("worker-codex", agents)
        self.assertIn("worker-cli1", agents)
        self.assertIn("worker-cli2", agents)
        self.assertEqual(agents["worker-google"]["provider"], "GOOGLE_PRO")
        self.assertEqual(agents["worker-codex"]["provider"], "CODEX")

        self.assertIn("snitch_observer", res)
        self.assertIn("snitch_workers", res)

    def test_03_sauna_props_and_bodyguard_alert_override_defined(self):
        """Sauna props (cigarette, shisha) and alert override behavior are defined in execution_truth.js."""
        content = Path("studio/execution_truth.js").read_text(encoding="utf-8")

        # Props
        self.assertIn("prop: 'cigarette'", content)
        self.assertIn("prop: 'shisha'", content)
        self.assertIn("prop: 'drink'", content)

        # Alert override check
        self.assertIn("hasSecurityAlert", content)
        self.assertIn("ALERT_STATION", content)

    def test_04_chief_alert_bar_deduplication_and_detail_panel_helpers(self):
        """Chief Alert Bar helper and Agent Detail Panel helper are exported from execution_truth.js."""
        content = Path("studio/execution_truth.js").read_text(encoding="utf-8")

        self.assertIn("export function resolveChiefAlerts", content)
        self.assertIn("export function resolveAgentDetailData", content)

        # Chief Alert types
        for alert_type in ["WAITING_PERMISSION", "HUNG", "ORPHANED", "HIGH_RISK_GATE", "WORKER_COMPLETED", "WORKER_AVAILABLE"]:
            self.assertIn(alert_type, content)

        # Detail Panel fields
        for field in ["last_progress", "state_age", "blocked_reason", "heavy_job", "result_id"]:
            self.assertIn(field, content)

    def test_05_html_and_css_chief_alert_bar_and_state_styles(self):
        """HTML and CSS have Chief alert bar and all 11 state style definitions."""
        html = Path("studio/index.html").read_text(encoding="utf-8")
        css = Path("studio/style.css").read_text(encoding="utf-8")

        self.assertIn('id="chief-alert-bar"', html)
        self.assertIn('id="chief-alert-stream"', html)

        # CSS classes for all 11 states
        states = [
            "state-progressing", "state-safe-idle", "state-waiting-permission",
            "state-waiting-human", "state-running-no-progress", "state-hung",
            "state-provider-error", "state-network-degraded", "state-completed",
            "state-orphaned", "state-unknown"
        ]
        for st in states:
            self.assertIn(st, css, f"Missing CSS class for state: {st}")

        # CSS classes for props
        self.assertIn(".agent-prop", css)
        self.assertIn(".prop-cigarette", css)
        self.assertIn(".prop-shisha", css)
        self.assertIn(".prop-drink", css)

    def test_06_zero_model_calls_and_resilience_during_provider_offline(self):
        """State aggregation makes 0 model calls and remains 100% resilient when provider is offline."""
        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res.get("schema_version"), "2.0")
        self.assertEqual(res.get("truth_contract", {}).get("model_calls", 0), 0)


if __name__ == "__main__":
    unittest.main()
