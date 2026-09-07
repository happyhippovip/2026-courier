import unittest
import json
import http.client
import threading
import time
import socketserver
import functools
from pathlib import Path
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.server as server


class TestDashboardFounderAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start a test server on an ephemeral port
        cls.port = 18080
        for attempt in range(10):
            try:
                handler = functools.partial(server.CommandCenterHandler, directory=str(server.DASHBOARD_DIR))
                cls.httpd = socketserver.TCPServer(("127.0.0.1", cls.port), handler)
                cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
                cls.server_thread.start()
                break
            except OSError:
                cls.port += 1

        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
            cls.httpd.server_close()

    def _request(self, method: str, path: str, body: dict = None) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body)

        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        conn.close()

        try:
            json_data = json.loads(data)
        except Exception:
            json_data = {"raw": data}
        return response.status, json_data

    def test_status_endpoint(self):
        status, data = self._request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "ONLINE")
        self.assertIn("founder_goals_total", data)
        self.assertEqual(data.get("active_cost_policy"), "ZERO_COST_ONLY")
        self.assertEqual(data.get("spend_eur"), 0.0)

    def test_founder_goals_endpoint(self):
        status, data = self._request("GET", "/api/founder/goals")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "SUCCESS")
        self.assertIsInstance(data.get("goals"), list)

    def test_monetization_readiness_endpoint(self):
        status, data = self._request("GET", "/api/monetization-readiness")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "SUCCESS")
        metrics = data.get("metrics", {})
        self.assertIn("time_saved_hours_estimated", metrics)
        self.assertIn("useful_dossiers_count", metrics)
        self.assertIn("verified_outcomes_count", metrics)
        self.assertIn("manual_rework_score_average", metrics)
        self.assertEqual(metrics.get("usage_provider_cost_eur"), 0.00)
        self.assertIn("ZERO_SPEND_ENFORCED", metrics.get("payment_intent_validation_state", ""))

    def test_crypto_sandbox_endpoint(self):
        status, data = self._request("GET", "/api/crypto/sandbox")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "DEMO_SANDBOX_ONLY")
        invariants = data.get("safety_invariants", {})
        self.assertFalse(invariants.get("real_funds_touched"))
        self.assertFalse(invariants.get("real_wallets_connected"))
        self.assertFalse(invariants.get("wallet_signing"))
        self.assertEqual(invariants.get("real_trades_count"), 0)
        self.assertEqual(invariants.get("autonomous_spend_limit_eur"), 0.0)

    def test_chaos_intake_and_dossier_lifecycle(self):
        # 1. Post chaotic founder notes
        chaos_text = """
        Goal: Build automated founder workspace validation suite
        Outcome: Provide 100% confidence in zero-coordination execution
        Decision: Write isolated unit tests for all REST API endpoints
        Assumption: Localhost tests run without network calls
        Question: Are all edge cases handled gracefully?
        TODO: Implement comprehensive HTTP endpoint tests
        Task: Verify chaos ingestion and dossier manifest updates
        Deliverable: tests/test_dashboard_founder_api.py
        Priority: P0: High-confidence verification
        """
        status, post_res = self._request("POST", "/api/founder/chaos", {
            "raw_chaos": chaos_text,
            "title": "API Verification Suite",
            "source": "unit_test"
        })
        self.assertEqual(status, 201)
        self.assertEqual(post_res.get("status"), "SUCCESS")
        dossier = post_res.get("dossier")
        self.assertIsNotNone(dossier)
        dossier_id = dossier.get("dossier_id")
        self.assertTrue(dossier_id.startswith("DOSSIER-"))
        self.assertEqual(dossier.get("title"), "API Verification Suite")
        self.assertGreaterEqual(len(dossier.get("goals")), 1)
        self.assertGreaterEqual(len(dossier.get("tasks")), 1)

        # 2. Get dossier by ID
        status, get_res = self._request("GET", f"/api/founder/dossier/{dossier_id}")
        self.assertEqual(status, 200)
        self.assertEqual(get_res.get("status"), "SUCCESS")
        self.assertEqual(get_res.get("dossier", {}).get("dossier_id"), dossier_id)

        # 3. Export dossier markdown
        status, export_res = self._request("POST", f"/api/founder/dossier/{dossier_id}/export", {})
        self.assertEqual(status, 200)
        self.assertEqual(export_res.get("status"), "SUCCESS")
        self.assertIn("markdown_content", export_res)
        self.assertIn("# 📋 Founder Execution Dossier", export_res.get("markdown_content"))

        # 4. List dossiers manifest
        status, list_res = self._request("GET", "/api/founder/dossiers")
        self.assertEqual(status, 200)
        dossiers = list_res.get("dossiers", [])
        dossier_ids = [d.get("dossier_id") for d in dossiers]
        self.assertIn(dossier_id, dossier_ids)

    def test_tasks_endpoint(self):
        status, data = self._request("GET", "/api/founder/tasks")
        self.assertEqual(status, 200)
        self.assertEqual(data.get("status"), "SUCCESS")
        self.assertIsInstance(data.get("missions"), list)

    def test_founder_review_actions(self):
        # 1. Accept action
        status, accept_res = self._request("POST", "/api/founder/review", {
            "action": "ACCEPT",
            "feedback": "LGTM, deliverable meets criteria.",
            "goal_id": "TEST-GOAL-1"
        })
        self.assertEqual(status, 200)
        self.assertEqual(accept_res.get("action"), "ACCEPT")
        self.assertEqual(accept_res.get("goal_status"), "SATISFIED")

        # 2. Revise action
        status, revise_res = self._request("POST", "/api/founder/review", {
            "action": "REVISE",
            "feedback": "Needs minor formatting adjustment.",
            "goal_id": "TEST-GOAL-1"
        })
        self.assertEqual(status, 200)
        self.assertEqual(revise_res.get("action"), "REVISE")
        self.assertEqual(revise_res.get("goal_status"), "PENDING")

        # 3. Reject action
        status, reject_res = self._request("POST", "/api/founder/review", {
            "action": "REJECT",
            "feedback": "Scope out of bounds.",
            "goal_id": "TEST-GOAL-1"
        })
        self.assertEqual(status, 200)
        self.assertEqual(reject_res.get("action"), "REJECT")
        self.assertEqual(reject_res.get("goal_status"), "BLOCKED")

        # 4. Next Action
        status, next_res = self._request("POST", "/api/founder/review", {
            "action": "NEXT_ACTION"
        })
        self.assertEqual(status, 200)
        self.assertIn("next_best_action", next_res)

    def test_seed_demo_endpoint(self):
        status, data = self._request("POST", "/api/founder/seed-demo", {})
        self.assertEqual(status, 201)
        self.assertEqual(data.get("status"), "SUCCESS")
        self.assertIn("dossier", data)
        self.assertIn("goal_id", data)


if __name__ == "__main__":
    unittest.main()
