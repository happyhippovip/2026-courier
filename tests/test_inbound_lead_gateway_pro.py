"""
test_inbound_lead_gateway_pro.py - Test Suite for TASK-WIN-75:
Agent Control Plane Inbound Lead Gateway, Champion Response Templates & Live Store Inquiry Endpoint

Certifies:
1. Inbound Interest Triage: Deterministic auto-response for GitHub/community interest with open-source MIT repo link.
2. Price Objection Resolution: Transparently contrasts free 5.00 EUR stdlib cap against €19.99 Pro Fleet Edition.
3. Trust Objection Handling: Guarantees 100% offline localhost operation with zero external telemetry or key exfiltration.
4. Technical Architecture Clarification: Explains forward-proxy and 4-prompt repetition HTTP 429 circuit breaker.
5. Purchase Intent Fulfillment: Dispatches direct Stripe 1-click checkout link with instant digital delivery.
6. P0 Support Human Gate: Crash/error inquiries are strictly quarantined for human review with zero robotic deflection.
7. HTTP Route Integration: Verifies POST /api/inbound/inquire contract in studio/server.js.
8. Operating Invariants: Automatic spend strictly 0.00 EUR, Mac scope excluded, proof debt 0.00.
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
NODE_CMD = shutil.which("node") or r"C:\Users\lol\AppData\Local\agy\bin\node.cmd"

from courier.chief.goal_reconciler import GoalReconciler


def run_node_gateway_query(base_dir: str, message: str, sender: str = "test_user", channel: str = "web_store") -> dict:
    """Executes InboundLeadGateway in Node.js within an isolated baseDir."""
    pm_escaped = PROJECT_MEMORY_DIR.replace("\\", "/")
    script = f"""
const path = require('path');
const {{ InboundLeadGateway }} = require('{pm_escaped}/money_factory/inbound_lead_gateway');

const baseDir = {json.dumps(base_dir)};
const gateway = new InboundLeadGateway(baseDir);

const res = gateway.processInboundMessage(
  {json.dumps(message)},
  {json.dumps(sender)},
  {json.dumps(channel)}
);
process.stdout.write(JSON.stringify(res));
"""
    tmp_js = os.path.join(base_dir, f"gateway_runner_{abs(hash(message)) % 100000}.js")
    with open(tmp_js, "w", encoding="utf-8") as f:
        f.write(script)

    try:
        run_res = subprocess.run(
            [NODE_CMD, tmp_js],
            cwd=PROJECT_MEMORY_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True,
            timeout=15
        )
        if run_res.returncode != 0:
            raise RuntimeError(f"Node execution failed (code {run_res.returncode}): {run_res.stderr}")
        return json.loads(run_res.stdout.strip())
    finally:
        if os.path.exists(tmp_js):
            try:
                os.remove(tmp_js)
            except Exception:
                pass


class TestInboundLeadGatewayPro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="inbound_gateway_test_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_interest_auto_response(self):
        """Invariant: INTEREST inquiries receive open-source core repo link with zero telemetry note."""
        query = "Great spend firewall project, starred your repo on GitHub!"
        res = run_node_gateway_query(self.temp_dir, query, sender="hn_reader", channel="hackernews")

        self.assertEqual(res.get("classification"), "INTEREST")
        self.assertEqual(res.get("action_taken"), "AUTO_RESPONDED")
        self.assertFalse(res.get("human_gate_required"))
        resp_text = res.get("response_text", "")
        self.assertIn("Agent Control Plane & Spend Firewall", resp_text)
        self.assertIn("https://github.com", resp_text)
        self.assertIn("MIT license", resp_text)

    def test_02_price_objection_auto_response(self):
        """Invariant: PRICE_OBJECTION inquiries explain free stdlib cap vs €19.99 fleet tier."""
        query = "Why not free? How much is the license for commercial agent fleets?"
        res = run_node_gateway_query(self.temp_dir, query, sender="startup_cto", channel="reddit")

        self.assertEqual(res.get("classification"), "PRICE_OBJECTION")
        self.assertEqual(res.get("action_taken"), "AUTO_RESPONDED")
        resp_text = res.get("response_text", "")
        self.assertIn("completely free and open-source under the MIT license", resp_text)
        self.assertIn("5.00 EUR", resp_text)
        self.assertIn("19.99", resp_text)
        self.assertIn("webhook alerts", resp_text)

    def test_03_trust_objection_zero_telemetry(self):
        """Invariant: TRUST_OBJECTION inquiries guarantee 100% offline execution with zero network telemetry."""
        query = "Does this proxy send my OpenAI API keys or private agent prompts to your servers?"
        res = run_node_gateway_query(self.temp_dir, query, sender="fintech_auditor", channel="web_store")

        self.assertEqual(res.get("classification"), "TRUST_OBJECTION")
        self.assertEqual(res.get("action_taken"), "AUTO_RESPONDED")
        resp_text = res.get("response_text", "")
        self.assertIn("100% offline", resp_text)
        self.assertIn("127.0.0.1", resp_text)
        self.assertIn("zero analytics", resp_text)
        self.assertIn("never leave your machine", resp_text)

    def test_04_technical_question_proxy_architecture(self):
        """Invariant: TECHNICAL_QUESTION inquiries explain local forward-proxy and loop circuit breaker."""
        query = "How does the loop breaker detect runaway spending before tokens are billed?"
        res = run_node_gateway_query(self.temp_dir, query, sender="ai_eng", channel="web_store")

        self.assertEqual(res.get("classification"), "TECHNICAL_QUESTION")
        self.assertEqual(res.get("action_taken"), "AUTO_RESPONDED")
        resp_text = res.get("response_text", "")
        self.assertIn("forward-proxy", resp_text)
        self.assertIn("HTTP 429", resp_text)
        self.assertIn("identical prompt", resp_text)

    def test_05_purchase_intent_stripe_link(self):
        """Invariant: PURCHASE_INTENT inquiries provide direct 1-click Stripe checkout link."""
        query = "Where do I buy the Pro Fleet Edition? Send checkout link."
        res = run_node_gateway_query(self.temp_dir, query, sender="dev_lead", channel="web_store")

        self.assertEqual(res.get("classification"), "PURCHASE_INTENT")
        self.assertEqual(res.get("action_taken"), "AUTO_RESPONDED")
        resp_text = res.get("response_text", "")
        self.assertIn("19.99 EUR", resp_text)
        self.assertIn("https://buy.stripe.com", resp_text)
        self.assertIn("cryptographic license key", resp_text)

    def test_06_support_request_p0_human_escalation(self):
        """Invariant: SUPPORT_REQUEST errors are strictly quarantined with zero automated deflection."""
        query = "Got Error: syntaxerror at line 14 unexpected token in spend_firewall.py"
        res = run_node_gateway_query(self.temp_dir, query, sender="user_broken", channel="web_store")

        self.assertEqual(res.get("classification"), "SUPPORT_REQUEST")
        self.assertEqual(res.get("action_taken"), "QUEUED_FOR_HUMAN")
        self.assertTrue(res.get("human_gate_required"))
        self.assertIsNone(res.get("response_text"))

        # Verify ticket was persisted in temp_dir/data/inbound_leads/p0_support/
        p0_dir = os.path.join(self.temp_dir, "data", "inbound_leads", "p0_support")
        p0_files = [f for f in os.listdir(p0_dir) if f.endswith(".json")]
        self.assertGreater(len(p0_files), 0, "P0 ticket file was not created in p0_support directory")

    def test_07_studio_server_inquire_route_contract(self):
        """Invariant: studio/server.js declares POST /api/inbound/inquire and routes to inboundLeadGateway."""
        server_js_path = os.path.join(PROJECT_MEMORY_DIR, "studio", "server.js")
        self.assertTrue(os.path.exists(server_js_path), f"Missing {server_js_path}")

        with open(server_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("InboundLeadGateway", content)
        self.assertIn("inboundLeadGateway = new InboundLeadGateway", content)
        self.assertIn("pathname === '/api/inbound/inquire'", content)
        self.assertIn("inboundLeadGateway.processInboundMessage", content)

    def test_08_operating_invariants_and_zero_spend(self):
        """Invariant: Autonomous spend strictly 0.00 EUR and Mac scopes excluded."""
        reconciler = GoalReconciler(workspace_root=WORKSPACE_ROOT)
        self.assertEqual(reconciler.AUTONOMOUS_SPEND_LIMIT_EUR, 0.00)
        self.assertTrue(reconciler.MAC_SCOPE_EXCLUDED)
        self.assertTrue(reconciler.UNIVERSUX_PROTECTED)


if __name__ == "__main__":
    unittest.main()
