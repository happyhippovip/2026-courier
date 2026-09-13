"""
test_peer_health_sync.py - Test suite for TASK-WIN-60
Certifies Cross-Platform Health Ping & Status Synchronization Protocol:
- Local node ping endpoint (/api/courier/ping)
- Supervisor and control plane status telemetry
- Standalone peer-health inspection
- Bidirectional peer sync and latency measurement
- Fail-closed unreachable peer handling
- CLI probe with zero-spend firewall validation
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.parse
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
from courier.tests.server_fixture import CourierServerTestCase

class TestPeerHealthSync(CourierServerTestCase):
    def http_get(self, endpoint):
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_01_local_ping_endpoint(self):
        """Verify /api/courier/ping returns valid host, supervisor metrics, checkpoint, and zero spend."""
        res = self.http_get("/api/courier/ping")
        self.assertTrue(res.get("success"), f"Ping failed: {res}")
        self.assertEqual(res.get("host"), "WINDOWS")
        self.assertIn("uptime_seconds", res)
        
        # Supervisor health
        sup = res.get("supervisor", {})
        self.assertEqual(sup.get("status"), "HEALTHY")
        self.assertIn("active_leases", sup)
        self.assertIn("active_locks", sup)
        
        # Control plane
        cp = res.get("control_plane", {})
        self.assertTrue(str(cp.get("checkpoint")).startswith("TASK-WIN-"))
        self.assertGreaterEqual(cp.get("certified_tasks_count", 0), 58)
        
        # Spend firewall
        fw = res.get("spend_firewall", {})
        self.assertEqual(float(fw.get("spend_eur", 0.0)), 0.0)
        self.assertEqual(float(fw.get("spend_limit_eur", 0.0)), 0.0)
        self.assertTrue(fw.get("invariant_satisfied"))

    def test_02_peer_health_standalone(self):
        """Verify /api/courier/peer-health without peer parameter reports local health and unqueried peer."""
        res = self.http_get("/api/courier/peer-health")
        self.assertTrue(res.get("success"), f"Peer health failed: {res}")
        
        local = res.get("local", {})
        self.assertEqual(local.get("host"), "WINDOWS")
        self.assertTrue(local.get("healthy"))
        self.assertEqual(float(local.get("spend_eur", 0.0)), 0.0)
        
        peer = res.get("peer", {})
        self.assertFalse(peer.get("queried"))

    def test_03_peer_health_loopback(self):
        """Verify /api/courier/peer-health with loopback peer confirms SYNCHRONIZED status and measures latency."""
        encoded_peer = urllib.parse.quote(self.base_url)
        res = self.http_get(f"/api/courier/peer-health?peer={encoded_peer}")
        self.assertTrue(res.get("success"), f"Loopback peer health failed: {res}")
        
        peer = res.get("peer", {})
        self.assertTrue(peer.get("queried"))
        self.assertTrue(peer.get("reachable"))
        self.assertGreaterEqual(peer.get("latency_ms", -1), 0)
        self.assertEqual(peer.get("sync_status"), "SYNCHRONIZED")
        self.assertEqual(peer.get("host"), "WINDOWS")
        self.assertEqual(float(peer.get("spend_eur", 0.0)), 0.0)

    def test_04_peer_health_unreachable_fail_closed(self):
        """Verify peer health handles unreachable/offline peer gracefully without crashing."""
        encoded_peer = urllib.parse.quote("http://127.0.0.1:59999")
        res = self.http_get(f"/api/courier/peer-health?peer={encoded_peer}")
        self.assertTrue(res.get("success"))
        
        local = res.get("local", {})
        self.assertTrue(local.get("healthy"))
        
        peer = res.get("peer", {})
        self.assertTrue(peer.get("queried"))
        self.assertFalse(peer.get("reachable"))
        self.assertEqual(peer.get("sync_status"), "UNREACHABLE")

    def test_05_cli_health_probe(self):
        """Verify CLI utility peer_health.py --probe --assert-zero-spend returns 0 and valid evidence."""
        cli_script = os.path.join(WORKSPACE_ROOT, "courier", "peer_health.py")
        proc = subprocess.run(
            [sys.executable, cli_script, "--probe", "--base-url", self.base_url, "--assert-zero-spend", "--json"],
            cwd=os.path.join(WORKSPACE_ROOT, "courier"),
            capture_output=True,
            text=True,
            timeout=15
        )
        self.assertEqual(proc.returncode, 0, f"CLI probe failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertTrue(data.get("success"))
        self.assertTrue(data.get("zero_spend_verified"))
        fingerprint = data.get("evidence_fingerprint", "")
        self.assertEqual(len(fingerprint), 64, "Evidence fingerprint must be a 64-character SHA-256 hex string")

if __name__ == "__main__":
    unittest.main()
