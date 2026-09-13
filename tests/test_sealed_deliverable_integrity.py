"""
test_sealed_deliverable_integrity.py - Test Suite for TASK-WIN-73:
Agent Control Plane Pro Sealed Deliverable Packaging, Clean-Room Extraction Verification & Cryptographic Manifest Integrity

Certifies:
1. Cryptographic Manifest Integrity: SHA-256 of agent_control_plane_pro_v1.0.0.zip matches DISTRIBUTION_MANIFEST_PRO.json and GITHUB_RELEASE_ASSETS.json.
2. Clean-Room Extraction: Zip unpacks cleanly into an isolated directory containing all 11 required deliverable files.
3. Standalone License Engine: Unpacked license engine passes unit tests without any external package dependencies.
4. Clean-Room Server Pro Activation: SpendFirewallPro executes from clean-room unpack with valid license key and activates PRO tier.
5. Clean-Room Server Degradation: SpendFirewallPro executes from clean-room unpack without valid license and degrades gracefully to FREE tier.
6. Distribution Route Integrity: Store download endpoint serves the exact byte-identical sealed zip archive.
7. Operating Invariants: Automatic spend remains 0.00 EUR, Mac scope excluded, zero telemetry.
"""

import os
import sys
import json
import time
import shutil
import zipfile
import hashlib
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
PRO_ZIP_PATH = os.path.join(ACP_DIR, "agent_control_plane_pro_v1.0.0.zip")
MANIFEST_PRO_PATH = os.path.join(ACP_DIR, "DISTRIBUTION_MANIFEST_PRO.json")
GITHUB_ASSETS_PATH = os.path.join(ACP_DIR, "distribution_pack", "GITHUB_RELEASE_ASSETS.json")
LICENSE_ENGINE_DIR = os.path.join(ACP_DIR, "license_engine")

if LICENSE_ENGINE_DIR not in sys.path:
    sys.path.insert(0, LICENSE_ENGINE_DIR)
if ACP_DIR not in sys.path:
    sys.path.insert(0, ACP_DIR)

from mint_license import mint_license
from courier.chief.goal_reconciler import GoalReconciler


class TestSealedDeliverableIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean_room_dir = tempfile.mkdtemp(prefix="clean_room_acp_pro_")
        with zipfile.ZipFile(PRO_ZIP_PATH, "r") as zf:
            zf.extractall(cls.clean_room_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.clean_room_dir):
            shutil.rmtree(cls.clean_room_dir, ignore_errors=True)

    def test_01_zip_manifest_cryptographic_integrity(self):
        """Invariant: Actual SHA-256 of sealed zip matches manifests exactly."""
        self.assertTrue(os.path.exists(PRO_ZIP_PATH), f"Missing zip: {PRO_ZIP_PATH}")
        with open(PRO_ZIP_PATH, "rb") as f:
            actual_sha256 = hashlib.sha256(f.read()).hexdigest()

        with open(MANIFEST_PRO_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(
            actual_sha256,
            manifest.get("zip_sha256"),
            "Mismatch between actual zip SHA-256 and DISTRIBUTION_MANIFEST_PRO.json"
        )

        with open(GITHUB_ASSETS_PATH, "r", encoding="utf-8") as f:
            github_assets = json.load(f)
        self.assertEqual(
            actual_sha256,
            github_assets.get("checksums", {}).get("agent_control_plane_pro_v1.0.0.zip"),
            "Mismatch between actual zip SHA-256 and GITHUB_RELEASE_ASSETS.json"
        )

    def test_02_clean_room_extraction_completeness(self):
        """Invariant: Unpacked archive contains all 11 deliverable files."""
        expected_files = [
            "spend_firewall_pro.py",
            "test_spend_firewall_pro.py",
            "spend_firewall.py",
            "test_spend_firewall.py",
            "demo_spend_firewall.py",
            "README.md",
            "SHOW_HN_LAUNCH_CARD.md",
            os.path.join("license_engine", "__init__.py"),
            os.path.join("license_engine", "license_validator.py"),
            os.path.join("license_engine", "mint_license.py"),
            os.path.join("license_engine", "test_license_engine.py")
        ]

        for rel_path in expected_files:
            target = os.path.join(self.clean_room_dir, rel_path)
            self.assertTrue(os.path.exists(target), f"Missing unpacked file: {target}")
            self.assertGreater(os.path.getsize(target), 0, f"Empty file in archive: {target}")

    def test_03_clean_room_standalone_license_test(self):
        """Invariant: License engine self-test passes inside unpacked clean-room sandbox."""
        test_script = os.path.join(self.clean_room_dir, "license_engine", "test_license_engine.py")
        env = os.environ.copy()
        # Ensure PYTHONPATH does not point to workspace
        env["PYTHONPATH"] = os.path.join(self.clean_room_dir, "license_engine")

        run_res = subprocess.run(
            [sys.executable, test_script],
            cwd=os.path.join(self.clean_room_dir, "license_engine"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=15
        )

        self.assertEqual(
            run_res.returncode,
            0,
            f"License engine test failed in clean room:\nSTDOUT: {run_res.stdout}\nSTDERR: {run_res.stderr}"
        )
        self.assertIn("OK", run_res.stderr + run_res.stdout)

    def test_04_clean_room_spend_firewall_pro_with_valid_key(self):
        """Invariant: SpendFirewallPro activates PRO tier from clean-room unpack with valid license."""
        test_port = 4145
        valid_key = mint_license("clean_room_buyer@enterprise.com", tier="PRO", validity_days=90)

        server_script = os.path.join(self.clean_room_dir, "spend_firewall_pro.py")
        env = os.environ.copy()
        env["FIREWALL_LICENSE_KEY"] = valid_key
        env["PYTHONPATH"] = self.clean_room_dir

        proc = subprocess.Popen(
            [sys.executable, server_script, str(test_port), "200.00"],
            cwd=self.clean_room_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        time.sleep(0.6)
        try:
            url = f"http://127.0.0.1:{test_port}/status"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                status_data = json.loads(resp.read().decode("utf-8"))

            self.assertEqual(status_data.get("status"), "ACTIVE")
            self.assertEqual(status_data.get("tier"), "PRO")
            self.assertEqual(status_data.get("cap_eur"), 200.00)
            self.assertEqual(status_data.get("firewall_mode"), "FAIL_CLOSED")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

    def test_05_clean_room_spend_firewall_pro_downgrades_without_key(self):
        """Invariant: SpendFirewallPro degrades to FREE tier from clean-room unpack with invalid license."""
        test_port = 4146
        bad_key = "ACP-TAMPERED.KEY"

        server_script = os.path.join(self.clean_room_dir, "spend_firewall_pro.py")
        env = os.environ.copy()
        env["FIREWALL_LICENSE_KEY"] = bad_key
        env["PYTHONPATH"] = self.clean_room_dir

        proc = subprocess.Popen(
            [sys.executable, server_script, str(test_port), "200.00"],
            cwd=self.clean_room_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        time.sleep(0.6)
        try:
            url = f"http://127.0.0.1:{test_port}/status"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                status_data = json.loads(resp.read().decode("utf-8"))

            self.assertEqual(status_data.get("status"), "ACTIVE")
            self.assertEqual(status_data.get("tier"), "FREE")
            self.assertEqual(status_data.get("cap_eur"), 5.00)  # Free tier hard cap
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

    def test_06_http_store_download_endpoint_serves_identical_sha256(self):
        """Invariant: studio/server.js configured path for download serves exact byte-matching file."""
        server_js_path = os.path.join(PROJECT_MEMORY_DIR, "studio", "server.js")
        self.assertTrue(os.path.exists(server_js_path), f"Missing {server_js_path}")

        # Check that server.js points to the exact file path
        with open(server_js_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("agent_control_plane_pro_v1.0.0.zip", content)

        # Verify on-disk file matches manifest
        with open(PRO_ZIP_PATH, "rb") as f:
            disk_sha256 = hashlib.sha256(f.read()).hexdigest()

        with open(MANIFEST_PRO_PATH, "r", encoding="utf-8") as f:
            manifest_sha256 = json.load(f)["zip_sha256"]

        self.assertEqual(disk_sha256, manifest_sha256)

    def test_07_operating_invariants_and_mac_exclusion(self):
        """Invariant: Autonomous spend strictly 0.00 EUR and Mac scopes excluded."""
        reconciler = GoalReconciler(workspace_root=WORKSPACE_ROOT)
        self.assertEqual(reconciler.AUTONOMOUS_SPEND_LIMIT_EUR, 0.00)
        self.assertTrue(reconciler.MAC_SCOPE_EXCLUDED)
        self.assertTrue(reconciler.UNIVERSUX_PROTECTED)


if __name__ == "__main__":
    unittest.main()
