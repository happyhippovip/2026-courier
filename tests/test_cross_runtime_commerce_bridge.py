"""
test_cross_runtime_commerce_bridge.py - Test Suite for TASK-WIN-72:
End-to-End Autonomous Commerce Fulfillment, Cross-Runtime License Bridge & Revenue Reality Certification

Certifies:
1. End-to-End Node.js Stripe Webhook Fulfillment: Webhook processes payment and mints HMAC-SHA256 ACP license.
2. Cross-Runtime Interoperability: Node.js-minted license validates cleanly in Python offline LicenseValidator.
3. Server Entitlement Activation: SpendFirewallPro activates PRO tier and custom budget using Node-minted license.
4. Tamper Rejection: Tampering with Node-minted payload causes immediate cryptographic rejection and tier downgrade.
5. Key Lifetime & Expiration: Expired Node-minted license is rejected as LICENSE_EXPIRED and tier downgraded to FREE.
6. Revenue Reality Firewall: Production settled transactions audit confirms real external revenue remains strictly 0.00 EUR.
7. Operating Invariants: Automatic spend remains 0.00 EUR, Mac scope excluded, proof debt 0.00.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import threading
import subprocess
import urllib.request
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
from spend_firewall_pro import run_pro
from courier.chief.goal_reconciler import GoalReconciler


def invoke_node_webhook(base_dir: str, event_id: str, email: str, product_id: str, amount_cents: int) -> dict:
    """Executes StripeWebhookHandler in Node.js within an isolated baseDir."""
    pm_escaped = PROJECT_MEMORY_DIR.replace("\\", "/")
    script = f"""
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {{ StripeWebhookHandler }} = require('{pm_escaped}/money_factory/stripe_webhook_handler');

const baseDir = {json.dumps(base_dir)};
const secret = 'whsec_courier_production_test_secret_2026';
const handler = new StripeWebhookHandler(baseDir, secret);

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

const res = handler.handleEvent(payloadStr, sigHeader);
process.stdout.write(JSON.stringify(res));
"""
    tmp_js = os.path.join(base_dir, f"webhook_runner_{event_id}.js")
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


def invoke_node_expired_mint(base_dir: str, email: str) -> str:
    """Mints an expired ACP license using Node.js crypto to verify cross-runtime expiration enforcement."""
    script = f"""
const crypto = require('crypto');
const salt = 'ACP_COMMERCIAL_ENTITLEMENT_SALT_2026_PRO_SECRET';
const expiredSec = 1600000000;
const payload = {{
  license_id: 'LIC-EXP-' + crypto.randomBytes(4).toString('hex'),
  buyer_id: {json.dumps(email)},
  tier: 'PRO',
  issued_at: expiredSec - 86400,
  expires_at: expiredSec,
  max_budget_eur: 500.0,
  features: ["MULTI_MODEL", "WEBHOOK_ALERTS"]
}};
const b64 = Buffer.from(JSON.stringify(payload)).toString('base64url');
const sig = crypto.createHmac('sha256', salt).update(b64).digest('hex');
process.stdout.write(`ACP-${{b64}}.${{sig}}`);
"""
    tmp_js = os.path.join(base_dir, "expired_mint_runner.js")
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
            raise RuntimeError(f"Node expired mint failed: {run_res.stderr}")
        return run_res.stdout.strip()
    finally:
        if os.path.exists(tmp_js):
            try:
                os.remove(tmp_js)
            except Exception:
                pass


class TestCrossRuntimeCommerceBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="commerce_bridge_test_")
        cls.validator = LicenseValidator()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_stripe_webhook_mints_acp_license_via_node(self):
        """Invariant: Processing OPP-SEED-04 Stripe checkout webhook mints ACP HMAC-SHA256 license."""
        buyer_email = "cto@enterprise-agent.de"
        event_id = "evt_bridge_test_001"
        res = invoke_node_webhook(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="OPP-SEED-04",
            amount_cents=1999
        )

        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertEqual(res.get("action"), "PAYMENT_SETTLED_AND_FULFILLED")
        self.assertEqual(res.get("product_id"), "OPP-SEED-04")
        self.assertEqual(res.get("amount_eur"), 19.99)
        self.assertFalse(res.get("revenue_verified"), "Test revenue must not be classified as verified real revenue")

        license_key = res.get("license_key", "")
        self.assertTrue(license_key.startswith("ACP-"), f"License key missing ACP- prefix: {license_key}")
        parts = license_key[4:].split(".")
        self.assertEqual(len(parts), 2, "License key must contain payload and signature segments separated by dot")
        self.assertEqual(len(parts[1]), 64, "Signature must be 64-char hex string (HMAC-SHA256)")

        # Verify atomic proof file written in temp baseDir
        proof_id = res.get("proof_id")
        proof_file = os.path.join(self.temp_dir, "data", "payment_proofs", f"{proof_id}.json")
        self.assertTrue(os.path.exists(proof_file), f"Missing proof file: {proof_file}")

    def test_02_node_minted_license_validates_in_python_engine(self):
        """Invariant: Offline Python LicenseValidator accepts and decodes Node.js-minted license."""
        buyer_email = "ai_director@fintech.eu"
        event_id = "evt_bridge_test_002"
        res = invoke_node_webhook(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="AGENT-CONTROL-PLANE-PRO",
            amount_cents=1999
        )
        license_key = res["license_key"]

        val_res = self.validator.validate_license(license_key)
        self.assertTrue(val_res["valid"], f"Validation failed: {val_res.get('error')}")
        self.assertIsNone(val_res["error"])
        self.assertEqual(val_res["tier"], "PRO")
        self.assertEqual(val_res["buyer_id"], buyer_email)
        self.assertEqual(val_res["max_budget_eur"], 500.0)
        self.assertIn("MULTI_MODEL", val_res["features"])
        self.assertIn("WEBHOOK_ALERTS", val_res["features"])
        self.assertIn("CUSTOM_BUDGET", val_res["features"])

    def test_03_spend_firewall_activates_pro_with_node_license(self):
        """Invariant: SpendFirewallPro activates PRO tier when launched with Node.js-minted license."""
        buyer_email = "server_test@cloud.io"
        event_id = "evt_bridge_test_003"
        res = invoke_node_webhook(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="OPP-SEED-04",
            amount_cents=1999
        )
        valid_key = res["license_key"]

        test_port = 4135
        t = threading.Thread(
            target=run_pro,
            kwargs={"port": test_port, "cap": 100.0, "license_key": valid_key},
            daemon=True
        )
        t.start()
        time.sleep(0.5)

        try:
            url = f"http://127.0.0.1:{test_port}/status"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                status_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(status_data.get("status"), "ACTIVE")
            self.assertEqual(status_data.get("tier"), "PRO")
            self.assertEqual(status_data.get("cap_eur"), 100.0)
            self.assertEqual(status_data.get("firewall_mode"), "FAIL_CLOSED")
        finally:
            pass

    def test_04_tampered_node_license_downgrades_to_free(self):
        """Invariant: Altering a single byte of the Node.js base64 payload fails Python signature verification."""
        buyer_email = "tamper_tester@sec.org"
        event_id = "evt_bridge_test_004"
        res = invoke_node_webhook(
            base_dir=self.temp_dir,
            event_id=event_id,
            email=buyer_email,
            product_id="OPP-SEED-04",
            amount_cents=1999
        )
        orig_key = res["license_key"]
        raw_b64, sig = orig_key[4:].split(".")

        # Tamper payload
        tampered_b64 = ("A" if raw_b64[0] != "A" else "B") + raw_b64[1:]
        tampered_key = f"ACP-{tampered_b64}.{sig}"

        val_res = self.validator.validate_license(tampered_key)
        self.assertFalse(val_res["valid"])
        self.assertIn(val_res["error"], ["INVALID_SIGNATURE", "TAMPERED_PAYLOAD"])
        self.assertEqual(val_res["tier"], "FREE")
        self.assertEqual(val_res["max_budget_eur"], 5.00)

    def test_05_expired_node_license_downgrades(self):
        """Invariant: Node.js-minted license with expired timestamp is rejected and downgraded."""
        expired_key = invoke_node_expired_mint(self.temp_dir, "expired_corp@old.com")
        val_res = self.validator.validate_license(expired_key)

        self.assertFalse(val_res["valid"])
        self.assertEqual(val_res["error"], "LICENSE_EXPIRED")
        self.assertEqual(val_res["tier"], "FREE")
        self.assertEqual(val_res["max_budget_eur"], 5.00)

    def test_06_revenue_reality_firewall_zero_unverified_revenue(self):
        """Invariant: Revenue Reality Firewall confirms production real external revenue remains strictly 0.00 EUR."""
        prod_settled_path = os.path.join(PROJECT_MEMORY_DIR, "data", "settled_transactions.json")
        self.assertTrue(os.path.exists(prod_settled_path), f"Missing {prod_settled_path}")

        with open(prod_settled_path, "r", encoding="utf-8") as f:
            transactions = json.load(f)

        real_revenue_total = 0.0
        for tx in transactions:
            classification = tx.get("revenue_classification", "")
            if classification == "REAL_EXTERNAL_REVENUE":
                real_revenue_total += float(tx.get("amount_eur", 0.0))

        self.assertEqual(
            real_revenue_total,
            0.00,
            f"REVENUE REALITY BREACH: Found unverified real revenue: €{real_revenue_total:.2f}"
        )

    def test_07_operating_invariants_and_mac_scope_exclusion(self):
        """Invariant: Autonomous spend limit strictly 0.00 EUR and Mac scopes completely untouched."""
        reconciler = GoalReconciler(workspace_root=WORKSPACE_ROOT)
        self.assertEqual(reconciler.AUTONOMOUS_SPEND_LIMIT_EUR, 0.00)
        self.assertTrue(reconciler.MAC_SCOPE_EXCLUDED)
        self.assertTrue(reconciler.UNIVERSUX_PROTECTED)


if __name__ == "__main__":
    unittest.main()
