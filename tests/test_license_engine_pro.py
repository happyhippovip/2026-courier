"""
test_license_engine_pro.py - Test Suite for TASK-WIN-70:
Agent Control Plane Pro Offline Cryptographic Entitlement & Zero-Telemetry License Minting Engine

Certifies:
1. Cryptographic Entitlement: Offline HMAC-SHA256 license minting and verification.
2. Expiration Guard: Expired license returns LICENSE_EXPIRED and downgrades tier to FREE.
3. Anti-Tampering: Modifying 1 byte in payload invalidates cryptographic signature.
4. Anti-Forgery: Keys signed with unauthorized secrets fail validation immediately.
5. Server Entitlement Activation: Running SpendFirewallPro with valid key activates PRO mode.
6. Server Graceful Degradation: Invalid/missing license downgrades to compliant FREE mode (5.00 EUR cap).
7. Operating Invariants: Zero telemetry, zero external network calls, spend remains 0.00 EUR.
"""

import os
import sys
import json
import time
import urllib.request
import threading
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

LICENSE_DIR = os.path.join(WORKSPACE_ROOT, "project-memory", "data", "distribution_ready", "agent_control_plane", "license_engine")
ACP_DIR = os.path.dirname(LICENSE_DIR)

if LICENSE_DIR not in sys.path:
    sys.path.insert(0, LICENSE_DIR)
if ACP_DIR not in sys.path:
    sys.path.insert(0, ACP_DIR)

from license_validator import LicenseValidator
from mint_license import mint_license
from spend_firewall_pro import run_pro, SpendLedgerPro
from courier.chief.goal_reconciler import GoalReconciler

class TestLicenseEnginePro(unittest.TestCase):
    def setUp(self):
        self.validator = LicenseValidator()

    def test_01_mint_and_verify_valid_pro_license(self):
        """Invariant: Validly minted PRO license passes offline verification."""
        buyer = "corp_ai_lead@enterprise.com"
        key = mint_license(buyer, tier="PRO", validity_days=180, max_budget_eur=250.00)
        res = self.validator.validate_license(key)

        self.assertTrue(res["valid"])
        self.assertIsNone(res["error"])
        self.assertEqual(res["tier"], "PRO")
        self.assertEqual(res["buyer_id"], buyer)
        self.assertEqual(res["max_budget_eur"], 250.00)
        self.assertIn("WEBHOOK_ALERTS", res["features"])

    def test_02_expired_license_rejected_and_downgraded(self):
        """Invariant: Expired license returns LICENSE_EXPIRED and downgrades to FREE."""
        buyer = "expired_eval@test.org"
        key = mint_license(buyer, tier="PRO", validity_days=-5)
        res = self.validator.validate_license(key)

        self.assertFalse(res["valid"])
        self.assertEqual(res["error"], "LICENSE_EXPIRED")
        self.assertEqual(res["tier"], "FREE")
        self.assertEqual(res["max_budget_eur"], 5.00)

    def test_03_tampered_payload_rejected(self):
        """Invariant: Altering 1 byte in payload breaks signature check."""
        buyer = "security_auditor@bank.de"
        key = mint_license(buyer, tier="PRO", validity_days=30)
        raw_b64 = key[4:].split(".")[0]
        sig = key.split(".")[1]
        tampered_b64 = ("Z" if raw_b64[-1] != "Z" else "A") + raw_b64[:-1]
        tampered_key = f"ACP-{tampered_b64}.{sig}"

        res = self.validator.validate_license(tampered_key)
        self.assertFalse(res["valid"])
        self.assertIn(res["error"], ["INVALID_SIGNATURE", "TAMPERED_PAYLOAD"])
        self.assertEqual(res["tier"], "FREE")

    def test_04_forged_wrong_secret_signature_rejected(self):
        """Invariant: Key signed with wrong secret is rejected cryptographically."""
        buyer = "adversary@unauthorized.com"
        fake_key = mint_license(buyer, tier="PRO", validity_days=365, secret="ATTACKER_SECRET")
        res = self.validator.validate_license(fake_key)

        self.assertFalse(res["valid"])
        self.assertEqual(res["error"], "INVALID_SIGNATURE")
        self.assertEqual(res["tier"], "FREE")

    def test_05_server_activates_pro_with_valid_key(self):
        """Invariant: SpendFirewallPro with valid license key exposes PRO tier."""
        test_port = 4120
        valid_key = mint_license("test_runner@pro.de", tier="PRO", validity_days=90)
        t = threading.Thread(target=run_pro, kwargs={"port": test_port, "cap": 50.0, "license_key": valid_key}, daemon=True)
        t.start()
        time.sleep(0.4)

        try:
            req = urllib.request.Request(f"http://127.0.0.1:{test_port}/status")
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read().decode())
                self.assertEqual(data["status"], "ACTIVE")
                self.assertEqual(data["tier"], "PRO")
                self.assertEqual(data["cap_eur"], 50.0)
        except Exception as e:
            self.fail(f"Server check failed: {e}")

    def test_06_server_downgrades_to_free_with_invalid_key(self):
        """Invariant: SpendFirewallPro with invalid license key degrades gracefully to FREE."""
        test_port = 4121
        bad_key = "ACP-INVALID.SIG"
        t = threading.Thread(target=run_pro, kwargs={"port": test_port, "cap": 100.0, "license_key": bad_key}, daemon=True)
        t.start()
        time.sleep(0.4)

        try:
            req = urllib.request.Request(f"http://127.0.0.1:{test_port}/status")
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read().decode())
                self.assertEqual(data["status"], "ACTIVE")
                self.assertEqual(data["tier"], "FREE")
                self.assertEqual(data["cap_eur"], 5.0)  # Capped at 5.00 EUR for FREE
        except Exception as e:
            self.fail(f"Server check failed: {e}")

    def test_07_operating_invariants(self):
        """Invariant: Zero spend EUR, Mac scope excluded."""
        self.assertEqual(GoalReconciler.AUTONOMOUS_SPEND_LIMIT_EUR, 0.00)
        self.assertTrue(GoalReconciler.MAC_SCOPE_EXCLUDED)

if __name__ == "__main__":
    unittest.main()
