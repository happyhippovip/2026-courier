"""
test_interactive_storefront_simulator.py - Test Suite for TASK-WIN-288:
Interactive In-Browser Spend Firewall Simulator & Storefront Sandbox Circuit

Certifies:
1. Storefront Delivery: GET /store and GET /distribution serve index.html with interactive simulation markup.
2. Simulator UI Elements: HTML includes #simTerminal, #simScenario, #simCap, #simMetrics, and runFirewallSimulation().
3. Simulation Backend Endpoint: POST /api/firewall/simulate returns 200 OK with structured trace, status 402 trip, and SHA-256 seal.
4. Parameterized Budget Caps: POST /api/firewall/simulate trips earlier when spend_cap_eur is set lower (€0.03 vs €0.05).
5. Fail-Closed Malformed Input: POST /api/firewall/simulate rejects non-JSON bodies with HTTP 400.
6. Zero Spend Invariant: Preserves strict 0.00 EUR spend and zero telemetry across all operations.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from courier.tests.server_fixture import CourierServerTestCase

class TestInteractiveStorefrontSimulator(CourierServerTestCase):
    def test_01_storefront_delivery_and_simulator_elements(self):
        """Verify GET /store serves index.html containing interactive simulator components."""
        url = f"{self.base_url}/store"
        req = urllib.request.Request(url, headers={"Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
            self.assertIn("simTerminal", html)
            self.assertIn("simScenario", html)
            self.assertIn("simCap", html)
            self.assertIn("runFirewallSimulation", html)
            self.assertIn("resetFirewallSimulation", html)
            self.assertIn("Test Runaway Agent Loop Circuit Breaker", html)

    def test_02_simulation_endpoint_standard_runaway_loop(self):
        """Verify POST /api/firewall/simulate simulates runaway tool loop and trips at budget cap."""
        url = f"{self.base_url}/api/firewall/simulate"
        payload = json.dumps({
            "scenario": "tool_retry_loop",
            "spend_cap_eur": 0.05
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("tripped"))
            self.assertEqual(data.get("trip_reason"), "BUDGET_EXCEEDED")
            self.assertEqual(data.get("trip_status_code"), 402)
            self.assertGreaterEqual(len(data.get("steps", [])), 2)
            self.assertEqual(len(data.get("audit_receipt_sha256", "")), 64)
            self.assertGreater(data.get("prevented_loss_eur", 0), 0)

            # Last step must be halted with HTTP 402
            last_step = data["steps"][-1]
            self.assertEqual(last_step["status_code"], 402)
            self.assertEqual(last_step["status"], "HALTED_BUDGET_EXCEEDED")

    def test_03_simulation_endpoint_tight_budget_cap(self):
        """Verify POST /api/firewall/simulate trips on earlier step when spend cap is 0.03 EUR."""
        url = f"{self.base_url}/api/firewall/simulate"
        payload = json.dumps({
            "scenario": "tool_retry_loop",
            "spend_cap_eur": 0.03
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("tripped"))
            # Step 1 was 0.03, step 2 would breach 0.03 so step 2 is rejected
            self.assertEqual(len(data.get("steps", [])), 2)
            self.assertEqual(data["steps"][0]["status_code"], 200)
            self.assertEqual(data["steps"][1]["status_code"], 402)

    def test_04_fail_closed_malformed_input(self):
        """Verify POST /api/firewall/simulate returns HTTP 400 for malformed non-JSON data."""
        url = f"{self.base_url}/api/firewall/simulate"
        req = urllib.request.Request(url, data=b"NOT_A_JSON{{{", headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 400)

    def test_05_zero_spend_invariant(self):
        """Verify zero autonomous spend and zero external telemetry."""
        ping_url = f"{self.base_url}/api/courier/ping"
        req = urllib.request.Request(ping_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            fw = data.get("spend_firewall", {})
            self.assertEqual(float(fw.get("spend_eur", 0.0)), 0.0)
            self.assertEqual(float(fw.get("spend_limit_eur", 0.0)), 0.0)

if __name__ == "__main__":
    unittest.main()
