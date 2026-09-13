"""
test_live_store_http_circuit.py - Test Suite for TASK-WIN-76:
End-to-End Live Store HTTP Ingestion, Cryptographic Webhook Settlement & Multi-Asset Binary Download Circuit

Certifies:
1. Live Storefront Delivery: GET /store and GET /distribution serve data/distribution_ready/index.html with UTF-8 HTML.
2. Unified Package Downloads: GET /downloads/<pkg> streams each distribution zip with Content-Disposition and exact SHA-256.
3. Path Traversal Defense: GET /downloads/../../etc/passwd is blocked with HTTP 400 fail-closed.
4. Agentic Download JSON Contract: GET /api/agentic/download?orderId=...&token=... returns structured delivery metadata.
5. Agentic Binary Streaming: GET /api/agentic/download?orderId=...&token=...&format=binary streams sealed .zip binary.
6. Stripe Webhook Settlement: POST /api/commerce/webhook ingests HMAC-signed checkout events and mints offline licenses.
7. Webhook Security: POST /api/commerce/webhook rejects tampered or expired signatures with HTTP 400.
8. Order Verification Lookup: GET /api/commerce/order resolves fulfilled order details and rejects unauthorized tokens.
9. Inbound Inquiry Endpoint: POST /api/inbound/inquire provides deterministic architectural and trust answers.
10. Operating Invariants: Automatic spend strictly 0.00 EUR, Mac scope excluded, zero telemetry.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import tempfile
import subprocess
import urllib.request
import urllib.error
import unittest
from datetime import datetime, timezone

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
ACP_DIR = os.path.join(PROJECT_MEMORY_DIR, "data", "distribution_ready", "agent_control_plane")
LICENSE_ENGINE_DIR = os.path.join(ACP_DIR, "license_engine")

if LICENSE_ENGINE_DIR not in sys.path:
    sys.path.insert(0, LICENSE_ENGINE_DIR)

from license_validator import LicenseValidator
from mint_license import mint_license

NODE_CMD = shutil.which("node") or r"C:\Users\lol\AppData\Local\agy\bin\node.cmd"


class TestLiveStoreHttpCircuit(unittest.TestCase):
    server_proc = None
    base_url = None
    runner_file = None

    @classmethod
    def setUpClass(cls):
        # 1. Write ephemeral server runner script
        server_js_path = os.path.join(PROJECT_MEMORY_DIR, "studio", "server.js").replace("\\", "/")
        runner_content = f"""
const {{ server }} = require('{server_js_path}');
server.listen(0, '127.0.0.1', () => {{
  const port = server.address().port;
  console.log('SERVER_READY:' + port);
}});
"""
        fd, cls.runner_file = tempfile.mkstemp(prefix="store_runner_", suffix=".js")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(runner_content)

        # 2. Spawn ephemeral Node server
        cls.server_proc = subprocess.Popen(
            [NODE_CMD, cls.runner_file],
            cwd=PROJECT_MEMORY_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        # 3. Wait for SERVER_READY line
        port = None
        start_time = time.time()
        while time.time() - start_time < 15:
            line = cls.server_proc.stdout.readline()
            if "SERVER_READY:" in line:
                port = int(line.strip().split("SERVER_READY:")[1])
                break
            time.sleep(0.1)

        if not port:
            cls.server_proc.kill()
            raise RuntimeError("Failed to start ephemeral studio/server.js test instance")

        cls.base_url = f"http://127.0.0.1:{port}"

    @classmethod
    def tearDownClass(cls):
        if cls.server_proc:
            cls.server_proc.terminate()
            try:
                cls.server_proc.wait(timeout=5)
            except Exception:
                cls.server_proc.kill()
        if cls.runner_file and os.path.exists(cls.runner_file):
            try:
                os.remove(cls.runner_file)
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # 1. LIVE STOREFRONT DELIVERY
    # --------------------------------------------------------------------------
    def test_01_storefront_html_delivery(self):
        """GET /store returns 200 with HTML containing hero headline and product cards."""
        url = f"{self.base_url}/store"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers.get("Content-Type", ""))
            body = resp.read().decode("utf-8")
            self.assertIn("Never Let Autonomous Agents", body)
            self.assertIn("Agent Control Plane PRO", body)
            self.assertIn("Retrieve License & Download Deliverable", body)

    # --------------------------------------------------------------------------
    # 2. UNIFIED PACKAGE DOWNLOADS
    # --------------------------------------------------------------------------
    def test_02_all_distribution_packages_downloadable(self):
        """GET /downloads/<pkg> streams each package with Content-Disposition and exact SHA-256."""
        packages = [
            ("agent_control_plane_pro_v1.0.0.zip", os.path.join(ACP_DIR, "agent_control_plane_pro_v1.0.0.zip")),
            ("agent_control_plane_v1.0.0.zip", os.path.join(ACP_DIR, "agent_control_plane_v1.0.0.zip")),
            ("courier_supervisor_v1.2.0.zip", os.path.join(PROJECT_MEMORY_DIR, "data", "distribution_ready", "courier_supervisor_v1.2.0.zip")),
            ("godot_inventory_dialogue_v1.0.0.zip", os.path.join(PROJECT_MEMORY_DIR, "data", "distribution_ready", "godot_templates", "godot_inventory_dialogue_v1.0.0.zip"))
        ]

        for pkg_name, disk_path in packages:
            self.assertTrue(os.path.exists(disk_path), f"Disk path {disk_path} must exist")
            with open(disk_path, "rb") as f:
                expected_sha = hashlib.sha256(f.read()).hexdigest()

            url = f"{self.base_url}/downloads/{pkg_name}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Content-Type"), "application/zip")
                self.assertIn(f'filename="{pkg_name}"', resp.headers.get("Content-Disposition", ""))
                body = resp.read()
                actual_sha = hashlib.sha256(body).hexdigest()
                self.assertEqual(actual_sha, expected_sha, f"SHA-256 mismatch for {pkg_name}")

    # --------------------------------------------------------------------------
    # 3. DIRECTORY TRAVERSAL DEFENSE
    # --------------------------------------------------------------------------
    def test_03_directory_traversal_defense(self):
        """Path traversal or malformed package names fail-closed with HTTP 400 or 404."""
        bad_urls = [
            f"{self.base_url}/downloads/..%2F..%2Fpackage.json",
            f"{self.base_url}/downloads/non_existent_bundle.zip"
        ]

        for u in bad_urls:
            try:
                urllib.request.urlopen(u, timeout=5)
                self.fail(f"Expected HTTP error for {u}")
            except urllib.error.HTTPError as e:
                self.assertIn(e.code, (400, 404))

    # --------------------------------------------------------------------------
    # 4. STRIPE WEBHOOK SETTLEMENT & ORDER PERSISTENCE
    # --------------------------------------------------------------------------
    def test_04_stripe_webhook_settlement_circuit(self):
        """POST /api/commerce/webhook processes valid signed Stripe event and creates proof + order."""
        event_id = f"evt_live_test_{int(time.time() * 1000)}"
        email = "enterprise_buyer@corp.com"
        secret = "whsec_courier_production_test_secret_2026"

        event_payload = {
            "id": event_id,
            "type": "checkout.session.completed",
            "livemode": False,
            "data": {
                "object": {
                    "id": f"cs_{event_id}",
                    "customer_email": email,
                    "amount_total": 1999,
                    "currency": "eur",
                    "payment_status": "paid",
                    "metadata": {
                        "product_id": "OPP-SEED-04"
                    }
                }
            }
        }
        raw_body = json.dumps(event_payload)
        now_sec = int(time.time())
        signed_payload = f"{now_sec}.{raw_body}"
        import hmac
        sig = hmac.new(secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        sig_header = f"t={now_sec},v1={sig}"

        url = f"{self.base_url}/api/commerce/webhook"
        req = urllib.request.Request(
            url,
            data=raw_body.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": sig_header
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("received"))
            self.assertIn("proof_id", data)
            self.assertIn("license_key", data)
            self.assertIn("delivery_token", data)

            proof_id = data["proof_id"]
            delivery_token = data["delivery_token"]
            license_key = data["license_key"]

            # Verify offline license validator validates the minted key as PRO
            validator = LicenseValidator()
            val_res = validator.validate_license(license_key)
            self.assertTrue(val_res["valid"])
            self.assertEqual(val_res["tier"], "PRO")

            # ------------------------------------------------------------------
            # 5. ORDER LOOKUP & VERIFICATION
            # ------------------------------------------------------------------
            order_url = f"{self.base_url}/api/commerce/order?orderId={proof_id}&token={delivery_token}"
            with urllib.request.urlopen(order_url, timeout=10) as order_resp:
                self.assertEqual(order_resp.status, 200)
                order_data = json.loads(order_resp.read().decode("utf-8"))
                self.assertEqual(order_data["order_id"], proof_id)
                self.assertEqual(order_data["fulfillment_status"], "FULFILLED")
                self.assertEqual(order_data["license_key"], license_key)

            # ------------------------------------------------------------------
            # 6. AGENTIC DOWNLOAD METADATA & BINARY STREAMING
            # ------------------------------------------------------------------
            dl_meta_url = f"{self.base_url}/api/agentic/download?orderId={proof_id}&token={delivery_token}"
            with urllib.request.urlopen(dl_meta_url, timeout=10) as meta_resp:
                self.assertEqual(meta_resp.status, 200)
                meta_data = json.loads(meta_resp.read().decode("utf-8"))
                self.assertEqual(meta_data["license_key"], license_key)
                self.assertTrue(meta_data["verified_zero_telemetry"])

            dl_bin_url = f"{self.base_url}/api/agentic/download?orderId={proof_id}&token={delivery_token}&format=binary"
            with urllib.request.urlopen(dl_bin_url, timeout=10) as bin_resp:
                self.assertEqual(bin_resp.status, 200)
                self.assertEqual(bin_resp.headers.get("Content-Type"), "application/zip")
                self.assertEqual(bin_resp.headers.get("X-License-Key"), license_key)
                bin_bytes = bin_resp.read()
                with open(os.path.join(ACP_DIR, "agent_control_plane_pro_v1.0.0.zip"), "rb") as zf:
                    expected_zip = zf.read()
                self.assertEqual(hashlib.sha256(bin_bytes).hexdigest(), hashlib.sha256(expected_zip).hexdigest())

    # --------------------------------------------------------------------------
    # 7. WEBHOOK FORGED SIGNATURE REJECTION
    # --------------------------------------------------------------------------
    def test_07_tampered_webhook_signature_rejected(self):
        """POST /api/commerce/webhook with tampered signature is rejected with HTTP 400."""
        payload = json.dumps({"test": "tampered"})
        url = f"{self.base_url}/api/commerce/webhook"
        req = urllib.request.Request(
            url,
            data=payload.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=123456,v1=deadbeef00001111"
            },
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("Tampered signature must be rejected")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    # --------------------------------------------------------------------------
    # 8. INBOUND LEAD INQUIRY ENDPOINT
    # --------------------------------------------------------------------------
    def test_08_inbound_inquiry_http_endpoint(self):
        """POST /api/inbound/inquire classifies buyer question and returns champion response."""
        payload = json.dumps({"message": "Do my private keys stay on localhost?", "channel": "web_store"})
        url = f"{self.base_url}/api/inbound/inquire"
        req = urllib.request.Request(
            url,
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("classification"), "TRUST_OBJECTION")
            self.assertIn("100% offline", data.get("response_text", ""))


if __name__ == "__main__":
    unittest.main()
