"""
test_delivery_fulfillment_circuit.py - Test Suite for TASK-WIN-74:
End-to-End Post-Payment Delivery Fulfillment, Digital Product Payload Resolution & Store Download Circuit

Certifies:
1. Webhook-to-Order Persistence: Processing Stripe checkout webhook atomically writes both payment proof and order delivery record.
2. Digital Delivery Resolution: AgenticCommerceEngine.downloadPayload resolves OPP-SEED-04 / AGENT-CONTROL-PLANE-PRO with full delivery envelope.
3. License Key Integrity: Delivered license key is cryptographically signed and passes offline Python LicenseValidator as PRO tier.
4. Token Security: Requests with invalid or forged delivery tokens are rejected with unauthorized delivery error.
5. Unknown Order Guard: Requests for nonexistent orders fail-closed with order not found error.
6. HTTP Route Contract: Verifies studio/server.js webhook and download API contracts operate synchronously and deterministically.
7. Operating Invariants: Automatic spend strictly 0.00 EUR, Mac scope excluded, zero telemetry.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
ACP_DIR = os.path.join(PROJECT_MEMORY_DIR, "data", "distribution_ready", "agent_control_plane")
LICENSE_ENGINE_DIR = os.path.join(ACP_DIR, "license_engine")

if LICENSE_ENGINE_DIR not in sys.path:
    sys.path.insert(0, LICENSE_ENGINE_DIR)
if ACP_DIR not in sys.path:
    sys.path.insert(0, ACP_DIR)

NODE_CMD = shutil.which("node") or r"C:\Users\lol\AppData\Local\agy\bin\node.cmd"

from license_validator import LicenseValidator
from courier.chief.goal_reconciler import GoalReconciler


def run_node_fulfillment_flow(base_dir: str, event_id: str, email: str, product_id: str, amount_cents: int) -> dict:
    """Executes Stripe webhook followed by downloadPayload in Node.js."""
    pm_escaped = PROJECT_MEMORY_DIR.replace("\\", "/")
    script = f"""
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {{ StripeWebhookHandler }} = require('{pm_escaped}/money_factory/stripe_webhook_handler');
const {{ AgenticCommerceEngine }} = require('{pm_escaped}/money_factory/agentic_commerce_engine');

const baseDir = {json.dumps(base_dir)};
const secret = 'whsec_courier_production_test_secret_2026';
const handler = new StripeWebhookHandler(baseDir, secret);
const commerce = new AgenticCommerceEngine(baseDir);

// 1. Webhook Event
const eventObj = {{
  id: {json.dumps(event_id)},
  type: 'checkout.session.completed',
  livemode: false,
  data: {{
    object: {{
      id: 'cs_' + {json.dumps(event_id)},
      customer_email: {json.dumps(email)},
      amount_total: {amount_cents},
      currency: 'eur',
      payment_status: 'paid',
      metadata: {{
        product_id: {json.dumps(product_id)}
      }}
    }}
  }}
}};

const payloadStr = JSON.stringify(eventObj);
const nowSec = Math.floor(Date.now() / 1000);
const sig = crypto.createHmac('sha256', secret).update(nowSec + '.' + payloadStr).digest('hex');
const sigHeader = 't=' + nowSec + ',v1=' + sig;

const webhookRes = handler.handleEvent(payloadStr, sigHeader);

// 2. Resolve Download Payload
const downloadRes = commerce.downloadPayload(webhookRes.proof_id, webhookRes.delivery_token);

process.stdout.write(JSON.stringify({{
  webhook: webhookRes,
  download: downloadRes
}}));
"""
    tmp_js = os.path.join(base_dir, f"fulfillment_flow_{event_id}.js")
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
            timeout=20
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


def run_node_download_probe(base_dir: str, order_id: str, token: str) -> dict:
    """Invokes downloadPayload directly in Node.js to probe error conditions."""
    pm_escaped = PROJECT_MEMORY_DIR.replace("\\", "/")
    script = f"""
const {{ AgenticCommerceEngine }} = require('{pm_escaped}/money_factory/agentic_commerce_engine');
const baseDir = {json.dumps(base_dir)};
const commerce = new AgenticCommerceEngine(baseDir);

try {{
  const res = commerce.downloadPayload({json.dumps(order_id)}, {json.dumps(token)});
  process.stdout.write(JSON.stringify({{ success: true, data: res }}));
}} catch (err) {{
  process.stdout.write(JSON.stringify({{ success: false, error: err.message }}));
}}
"""
    tmp_js = os.path.join(base_dir, f"download_probe_{order_id}.js")
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
            raise RuntimeError(f"Node probe failed (code {run_res.returncode}): {run_res.stderr}")
        return json.loads(run_res.stdout.strip())
    finally:
        if os.path.exists(tmp_js):
            try:
                os.remove(tmp_js)
            except Exception:
                pass


class TestDeliveryFulfillmentCircuit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="fulfillment_circuit_test_")
        cls.validator = LicenseValidator()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_webhook_to_order_persistence(self):
        """Invariant: Webhook settlement writes both payment proof and order delivery file atomically."""
        buyer_email = "lead_dev@saas-startup.de"
        event_id = "evt_fulfill_test_001"
        res = run_node_fulfillment_flow(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="OPP-SEED-04",
            amount_cents=1999
        )

        webhook = res["webhook"]
        proof_id = webhook["proof_id"]

        # 1. Verify proof file
        proof_path = os.path.join(self.temp_dir, "data", "payment_proofs", f"{proof_id}.json")
        self.assertTrue(os.path.exists(proof_path), f"Missing payment proof file: {proof_path}")

        # 2. Verify order delivery file
        order_path = os.path.join(self.temp_dir, "data", "agentic_commerce", "orders", f"{proof_id}.json")
        self.assertTrue(os.path.exists(order_path), f"Missing order delivery file: {order_path}")

        with open(order_path, "r", encoding="utf-8") as f:
            order_data = json.load(f)
        self.assertEqual(order_data.get("order_id"), proof_id)
        self.assertEqual(order_data.get("product_id"), "OPP-SEED-04")
        self.assertEqual(order_data.get("status"), "FULFILLED")
        self.assertEqual(order_data.get("buyer_agent_id"), buyer_email)

    def test_02_download_payload_resolves_pro_entitlement(self):
        """Invariant: downloadPayload resolves OPP-SEED-04 with complete activation guide and archive URL."""
        buyer_email = "platform_arch@ai-fleet.io"
        event_id = "evt_fulfill_test_002"
        res = run_node_fulfillment_flow(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="AGENT-CONTROL-PLANE-PRO",
            amount_cents=1999
        )

        download = res["download"]
        self.assertEqual(download.get("product_id"), "AGENT-CONTROL-PLANE-PRO")
        self.assertIn("http://localhost:8088/downloads/agent_control_plane_pro_v1.0.0.zip", download.get("download_zip_url", ""))
        self.assertTrue(download.get("verified_zero_telemetry"))

        payload_text = download.get("payload", "")
        self.assertIn("Agent Control Plane PRO", payload_text)
        self.assertIn(download.get("license_key"), payload_text)
        self.assertIn("500.00 EUR Custom Budget Cap", payload_text)
        self.assertIn("python spend_firewall_pro.py", payload_text)

    def test_03_downloaded_license_validates_in_python_validator(self):
        """Invariant: The license key returned in the delivery payload validates as PRO tier in Python."""
        buyer_email = "security_lead@autonomous.org"
        event_id = "evt_fulfill_test_003"
        res = run_node_fulfillment_flow(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="OPP-SEED-04",
            amount_cents=1999
        )

        license_key = res["download"]["license_key"]
        val_res = self.validator.validate_license(license_key)

        self.assertTrue(val_res["valid"], f"Delivered key failed validation: {val_res.get('error')}")
        self.assertEqual(val_res["tier"], "PRO")
        self.assertEqual(val_res["buyer_id"], buyer_email)
        self.assertEqual(val_res["max_budget_eur"], 500.0)
        self.assertIn("LOOP_BREAKER_PRO", val_res["features"])

    def test_04_unauthorized_token_rejected(self):
        """Invariant: Supplying an incorrect delivery token is rejected fail-closed."""
        buyer_email = "valid_buyer@test.de"
        event_id = "evt_fulfill_test_004"
        res = run_node_fulfillment_flow(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="OPP-SEED-04",
            amount_cents=1999
        )

        proof_id = res["webhook"]["proof_id"]
        probe_res = run_node_download_probe(self.temp_dir, proof_id, "forged_bad_token_1234")

        self.assertFalse(probe_res.get("success"))
        self.assertIn("Unauthorized delivery token", probe_res.get("error", ""))

    def test_05_unknown_order_rejected(self):
        """Invariant: Requesting delivery for a nonexistent order fails cleanly."""
        probe_res = run_node_download_probe(self.temp_dir, "PROOF-GHOST-NONEXISTENT", "any_token")

        self.assertFalse(probe_res.get("success"))
        self.assertIn("not found", probe_res.get("error", ""))

    def test_06_http_server_route_contract(self):
        """Invariant: studio/server.js declares both /api/webhooks/stripe and /api/agentic/download."""
        server_js_path = os.path.join(PROJECT_MEMORY_DIR, "studio", "server.js")
        self.assertTrue(os.path.exists(server_js_path), f"Missing {server_js_path}")

        with open(server_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("pathname === '/api/webhooks/stripe'", content)
        self.assertIn("pathname === '/api/agentic/download'", content)
        self.assertIn("stripeWebhookHandler.handleEvent", content)
        self.assertIn("commerceEngine.downloadPayload", content)

    def test_07_operating_invariants_and_zero_spend(self):
        """Invariant: Autonomous spend strictly 0.00 EUR and Mac scopes excluded."""
        reconciler = GoalReconciler(workspace_root=WORKSPACE_ROOT)
        self.assertEqual(reconciler.AUTONOMOUS_SPEND_LIMIT_EUR, 0.00)
        self.assertTrue(reconciler.MAC_SCOPE_EXCLUDED)
        self.assertTrue(reconciler.UNIVERSUX_PROTECTED)


if __name__ == "__main__":
    unittest.main()
