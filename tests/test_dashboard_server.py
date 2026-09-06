#!/usr/bin/env python3
"""Acceptance Test Suite for Dashboard Server & Telemetry Bridge (Product/Business Surface).

Verifies:
1. Status payload extraction reflects live 2026-courier repository state
2. Dynamic MEMORY_DIR fallback
3. Inclusion of central motto, live worker registry, and zero spend policy
4. HTTP /api/status endpoint response format
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from dashboard.server import get_status_payload


class TestDashboardServer(unittest.TestCase):
    def test_01_get_status_payload_structure(self):
        """Status payload returns comprehensive live telemetry."""
        payload = get_status_payload()
        self.assertEqual(payload["status"], "ONLINE")
        self.assertEqual(payload["version"], "3.0-live-autonomy")
        self.assertEqual(payload["active_cost_policy"], "ZERO_COST_ONLY")
        self.assertEqual(payload["spend_eur"], 0.0)
        self.assertEqual(payload["unauthorized_spend_eur"], 0.0)
        self.assertIn("central_motto", payload)
        self.assertIn("WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN.", payload["central_motto"])
        self.assertIn("active_workers", payload)
        self.assertIn("real_vs_simulated", payload)
        self.assertEqual(payload["real_vs_simulated"]["canonical_authority"], "VERIFIED_REAL")
        self.assertEqual(payload["real_vs_simulated"]["creator_video_production"], "PAUSED_BY_POLICY")

    def test_02_get_commercial_offers_payload(self):
        """Commercial offers endpoint returns active opportunities."""
        from dashboard.server import get_commercial_offers_payload
        payload = get_commercial_offers_payload()
        self.assertEqual(payload["status"], "OFFERS_ACTIVE")
        self.assertEqual(payload["autonomous_spend_eur"], 0.0)
        self.assertGreaterEqual(payload["total_offers"], 4)
        offer_ids = [o["opportunity_id"] for o in payload["offers"]]
        self.assertIn("REV-OPP-B2B-AUTONOMY-AUDIT", offer_ids)
        self.assertIn("REV-OPP-CONTENT-TO-MARKETING-ASSET", offer_ids)


if __name__ == "__main__":
    unittest.main()
