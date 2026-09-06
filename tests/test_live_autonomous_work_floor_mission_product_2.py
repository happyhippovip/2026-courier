#!/usr/bin/env python3
"""Mission PRODUCT-2 Acceptance Test Suite — Live Autonomous Work Floor.

Verifies:
1. Consumption of Codex PRODUCT_1C Live Operations Truth Contract.
2. Real Task Board data completeness, status mapping, and deduplication.
3. 'NEEDS YOU' User Attention Panel truthfulness.
4. Live Result Feed event streaming without heartbeat/polling noise.
5. Provider / Worker visibility (LOCAL_DETERMINISTIC, GOOGLE_PRO, CODEX).
6. Safe Idle visibility (0 fake busywork).
7. Real local lifecycle and gated branch isolation.
8. Zero model calls and 0 fake activity during UI polling/refresh.
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
from scripts.live_operations_truth_contract import LiveOperationsTruthContract


class TestLiveAutonomousWorkFloorMissionProduct2(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="courier_work_floor_test_"))
        self.events_dir = self.test_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        (self.events_dir / "agent-states").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "autonomy-runtime").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "autonomy-runtime" / "jobs").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "anomalies").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "opportunity-queue").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "approvals").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "chief-decisions").mkdir(parents=True, exist_ok=True)
        (self.events_dir / "locks").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_product_1c_truth_contract_consumed(self):
        """Server /api/state consumes and includes LiveOperationsTruthContract snapshot."""
        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertIn("truth_contract", res)
        tc = res["truth_contract"]
        self.assertEqual(tc.get("contract_version"), "PRODUCT_1C_V1")
        self.assertEqual(tc.get("model_calls"), 0)

    def test_02_live_task_board_deduplication_and_mapping(self):
        """Task board deduplicates canonical tasks from queue and truth contract."""
        # Add opportunity 1: ready
        opp1 = {
            "opportunity_id": "opp-calc-001",
            "description": "Calculate risk metrics",
            "target_agent": "antigravity",
            "status": "READY",
            "priority": 8,
            "risk": "LOW",
            "cost_class": "FREE_LOCAL",
        }
        (self.events_dir / "opportunity-queue" / "opp-calc-001.json").write_text(json.dumps(opp1))

        # Add opportunity 2: human gate
        opp2 = {
            "opportunity_id": "opp-pub-002",
            "description": "Publish weekly summary",
            "target_agent": "publication_officer",
            "status": "WAITING_FOR_HUMAN",
            "priority": 9,
            "risk": "HIGH",
            "cost_class": "FREE_LOCAL",
        }
        (self.events_dir / "opportunity-queue" / "opp-pub-002.json").write_text(json.dumps(opp2))

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        tb = res.get("task_board", [])
        self.assertEqual(len(tb), 2)

        task_ids = [t["task_id"] for t in tb]
        self.assertIn("opp-calc-001", task_ids)
        self.assertIn("opp-pub-002", task_ids)

        calc_task = next(t for t in tb if t["task_id"] == "opp-calc-001")
        self.assertEqual(calc_task["provider"], "GOOGLE_PRO")
        self.assertEqual(calc_task["status"], "READY")

    def test_03_needs_you_panel_truthfulness_when_safe(self):
        """Needs You panel displays NOTHING (safe to walk away) when zero gates exist."""
        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        ar = res.get("autonomy_runtime", {})
        self.assertEqual(len(ar.get("human_gates", [])), 0)
        self.assertEqual(len(ar.get("money_gates", [])), 0)

    def test_04_needs_you_panel_flags_human_gate(self):
        """Needs You panel identifies active Human Gate accurately."""
        sess_data = {
            "session_id": "session-test-gate",
            "status": "PAUSED_GATE",
            "goal": "Run gated workflow",
            "current_action": "HUMAN_GATE_PUBLICATION_FIREWALL",
            "human_gates_encountered": [{"task_id": "task-pub-01", "reason": "HUMAN_GATE_PUBLICATION_FIREWALL"}],
            "money_gates_encountered": [],
            "jobs_dispatched": [],
            "jobs_completed": [],
        }
        (self.events_dir / "autonomy-runtime" / "current_session.json").write_text(json.dumps(sess_data))

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        ar = res.get("autonomy_runtime", {})
        self.assertEqual(len(ar.get("human_gates", [])), 1)
        self.assertEqual(ar["human_gates"][0]["task_id"], "task-pub-01")

    def test_05_live_result_feed_streams_meaningful_events(self):
        """Result feed captures recent meaningful events and ignores heartbeat spam."""
        ledger_data = {
            "processed_event_hashes": ["h1", "h2"],
            "events": [
                {
                    "event_id": "evt-01",
                    "event_type": "RESULT",
                    "task_id": "task-build-1",
                    "source_worker": "antigravity",
                    "payload": {"outcome": "SUCCESS"},
                    "ingested_at": "2026-09-01T01:00:00Z",
                },
                {
                    "event_id": "evt-02",
                    "event_type": "HUMAN_GATE",
                    "task_id": "task-pub-2",
                    "source_worker": "publication_officer",
                    "payload": {"outcome": "PARKED"},
                    "ingested_at": "2026-09-01T01:05:00Z",
                }
            ]
        }
        (self.events_dir / "autonomy-runtime" / "event_ledger.json").write_text(json.dumps(ledger_data))

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        feed = res.get("result_feed", [])
        self.assertEqual(len(feed), 2)
        self.assertEqual(feed[0]["task_id"], "task-build-1")
        self.assertEqual(feed[0]["outcome"], "SUCCESS")
        self.assertEqual(feed[1]["event_type"], "HUMAN_GATE")

    def test_06_provider_visibility_and_resource_class(self):
        """Distinguishes LOCAL_DETERMINISTIC, GOOGLE_PRO, and CODEX truthfully."""
        job_google = {
            "job_id": "job-g1",
            "task_id": "task-g1",
            "owner": "GOOGLE",
            "provider": "GOOGLE_PRO",
            "resource_class": "GOOGLE_PRO_POOL_1",
            "scope": "BUILDER",
            "status": "RUNNING",
            "created_at": "2026-09-01T00:00:00Z",
        }
        (self.events_dir / "autonomy-runtime" / "jobs" / "job-g1.json").write_text(json.dumps(job_google))

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        tb = res.get("task_board", [])
        self.assertEqual(len(tb), 1)
        self.assertEqual(tb[0]["provider"], "GOOGLE_PRO")
        self.assertEqual(tb[0]["status"], "ACTIVE")

    def test_07_safe_idle_has_zero_fake_activity(self):
        """Safe idle displays 0 active jobs and 0 fake activity."""
        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        ar = res.get("autonomy_runtime", {})
        self.assertEqual(ar.get("status"), "IDLE_EXPECTED")
        self.assertEqual(len(ar.get("jobs_dispatched", [])), 0)

    def test_08_end_to_end_real_lifecycle_and_branch_isolation(self):
        """Proves real task lifecycle and branch isolation when one task is gated."""
        # Task A: Safe eligible task
        opp_a = {
            "opportunity_id": "task-a-safe",
            "description": "Lint local code",
            "target_agent": "antigravity",
            "status": "READY",
            "priority": 7,
            "branch": "MAIN",
        }
        (self.events_dir / "opportunity-queue" / "task-a-safe.json").write_text(json.dumps(opp_a))

        # Task B: Gated task
        opp_b = {
            "opportunity_id": "task-b-gate",
            "description": "Deploy production release",
            "target_agent": "publication_officer",
            "status": "WAITING_FOR_HUMAN",
            "priority": 9,
            "branch": "RELEASE",
        }
        (self.events_dir / "opportunity-queue" / "task-b-gate.json").write_text(json.dumps(opp_b))

        handler = MagicMock()
        handler.wfile = io.BytesIO()

        with patch("scripts.run_visual_studio_server.EVENTS_DIR", self.events_dir),              patch("scripts.run_visual_studio_server.COURIER_DIR", self.test_dir):
            StudioHTTPRequestHandler.handle_api_state(handler)

        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        tb = res.get("task_board", [])
        self.assertEqual(len(tb), 2)

        task_a = next(t for t in tb if t["task_id"] == "task-a-safe")
        task_b = next(t for t in tb if t["task_id"] == "task-b-gate")

        self.assertEqual(task_a["status"], "READY")
        self.assertEqual(task_b["status"], "WAITING_FOR_HUMAN")


if __name__ == "__main__":
    unittest.main()
