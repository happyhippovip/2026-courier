import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.google_pool_controller import GooglePoolController
from scripts.multi_account_workspace_switch import ThreePoolResourceRegistry


class GooglePoolControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.repo = Path(self.tmp) / "2026-courier"; self.repo.mkdir(parents=True)
        (self.repo / ".git").mkdir(); (self.repo / "events/resource-intelligence").mkdir(parents=True)
        self.controller = GooglePoolController(self.repo)
        self.controller.engine.canonical_root = str(self.repo)
        reg = ThreePoolResourceRegistry(self.repo)
        reg.load_registry()
        for alias in ("GOOGLE_PRO_POOL_1", "GOOGLE_PRO_POOL_2"):
            reg.update_pool(alias, authorization_state="AUTHORIZED", verification_state="VERIFIED", capacity_state="AVAILABLE", status="VERIFIED")

    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_four_pools_and_pool4_not_configured(self):
        pools = self.controller.status()["pools"]
        self.assertEqual(set(pools), {"GOOGLE_PRO_POOL_1", "GOOGLE_PRO_POOL_2", "GOOGLE_PRO_POOL_3", "GOOGLE_PRO_POOL_4"})
        self.assertEqual(pools["GOOGLE_PRO_POOL_4"]["authorization_state"], "NOT_CONFIGURED")

    def test_exhaustion_recommends_not_logs_in(self):
        self.controller.register_observation("GOOGLE_PRO_POOL_1", "EXHAUSTED", 0, 31)
        result = self.controller.recommend("GOOGLE_PRO_POOL_1")
        self.assertEqual(result["status"], "ACCOUNT_SWITCH_RECOMMENDED")
        self.assertTrue(result["account_switch_required"])

    def test_checkpoint_then_human_boundary_then_verified_switch(self):
        pre = self.controller.prepare_switch("GOOGLE_PRO_POOL_1", "GOOGLE_PRO_POOL_2", "task-x")
        self.assertEqual(pre["status"], "SAFE_TO_SWITCH")
        self.assertEqual(self.controller.verify_switch("GOOGLE_PRO_POOL_2")["status"], "AUTH_NOT_CONFIRMED")
        self.assertEqual(self.controller.verify_switch("GOOGLE_PRO_POOL_2", human_auth_confirmed=True)["status"], "CONTINUATION_READY")

    def test_pool4_requires_payment_approval(self):
        self.assertEqual(self.controller.prepare_switch("GOOGLE_PRO_POOL_1", "GOOGLE_PRO_POOL_4")["status"], "PAYMENT_APPROVAL_REQUIRED")

    def test_pool2_to_pool3_reuses_same_local_workspace_contract(self):
        self.controller.prepare_switch("GOOGLE_PRO_POOL_2", "GOOGLE_PRO_POOL_3", "task-y")
        result = self.controller.verify_switch("GOOGLE_PRO_POOL_3", human_auth_confirmed=True)
        self.assertEqual(result["status"], "CONTINUATION_READY")
        self.assertTrue(result["same_workspace"])

    def test_all_unavailable_waits_and_no_percent_sum(self):
        for alias in ("GOOGLE_PRO_POOL_1", "GOOGLE_PRO_POOL_2"):
            self.controller.register_observation(alias, "EXHAUSTED", 0, 30)
        result = self.controller.recommend("GOOGLE_PRO_POOL_1")
        self.assertEqual(result["status"], "RESOURCE_WAIT")
        self.assertNotIn("total_quota", self.controller.status()["pools"])


if __name__ == '__main__': unittest.main()
