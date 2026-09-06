"""Independent adversarial probes for Mission 175G resource-history semantics."""
import tempfile
import unittest
from pathlib import Path

from scripts.resource_benchmark_manager import ResourceBenchmarkManager


class ResourceHistoryAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = ResourceBenchmarkManager(repo_dir=Path(self.temp.name))
        self.obs = self.manager.load_observations()

    def tearDown(self):
        self.temp.cleanup()

    def _one(self, observation_id):
        return next(item for item in self.obs if item.observation_id == observation_id)

    def test_reset_boundary_is_not_enforced_by_delta_calculation(self):
        before = self._one("resobs-20260831-132400-google")
        after = self._one("resobs-20260831-143200-google")
        result = self.manager.calculate_delta(before, after)
        self.assertEqual(50.0, result["five_hour_capacity_delta_pct_points"])

    def test_unknown_time_observation_can_still_be_used_for_delta(self):
        exact = self._one("resobs-20260831-110000-openai")
        unknown = self._one("resobs-20260831-unknown-openai")
        result = self.manager.calculate_delta(exact, unknown)
        self.assertEqual(-95.0, result["five_hour_capacity_delta_pct_points"])

    def test_cross_provider_account_and_model_are_rejected(self):
        openai = self._one("resobs-20260831-110000-openai")
        google = self._one("resobs-20260831-110000-google")
        with self.assertRaises(ValueError): self.manager.calculate_delta(openai, google)
        pool2 = self._one("resobs-20260831-223800-google-gemini-latest")
        with self.assertRaises(ValueError): self.manager.calculate_delta(google, pool2)

    def test_dataset_keeps_unknown_timestamp_and_non_additive_latest_pools(self):
        self.assertEqual("UNKNOWN", self._one("resobs-20260831-unknown-openai").observed_at)
        latest_gemini = self._one("resobs-20260831-223800-google-gemini-latest")
        latest_models = self._one("resobs-20260831-223800-google-claudegpt-latest")
        self.assertNotEqual(latest_gemini.model_pool, latest_models.model_pool)


if __name__ == "__main__": unittest.main()
