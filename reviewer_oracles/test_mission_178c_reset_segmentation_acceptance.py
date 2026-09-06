"""Independent adversarial probes for the 178C reset-segmentation delta (Remediated)."""
from dataclasses import replace
import tempfile
import unittest
from pathlib import Path

from scripts.resource_benchmark_manager import ResourceBenchmarkManager


class ResetSegmentationAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = ResourceBenchmarkManager(repo_dir=Path(self.temp.name))
        self.obs = {o.observation_id: o for o in self.manager.load_observations()}

    def tearDown(self):
        self.temp.cleanup()

    def test_forged_segment_id_bypasses_google_reset_boundary(self):
        before = self.obs["resobs-20260831-132400-google"]
        reset = self.obs["resobs-20260831-142100-google-reset"]
        forged = replace(reset, five_hour_segment_id=before.five_hour_segment_id)
        with self.assertRaises(ValueError):
            self.manager.calculate_five_hour_delta(before, forged)

    def test_forged_segment_id_bypasses_openai_five_hour_reset(self):
        before = self.obs["resobs-20260831-unknown-openai"]
        latest = self.obs["resobs-20260831-223800-openai-latest"]
        forged = replace(latest, five_hour_segment_id=before.five_hour_segment_id)
        with self.assertRaises(ValueError):
            self.manager.calculate_five_hour_delta(before, forged)

    def test_unknown_timestamp_can_still_calculate_same_segment_delta(self):
        exact = self.obs["resobs-20260831-110000-openai"]
        unknown = self.obs["resobs-20260831-unknown-openai"]
        with self.assertRaises(ValueError):
            self.manager.calculate_five_hour_delta(exact, unknown)

    def test_real_segment_boundary_is_rejected_without_forgery(self):
        before = self.obs["resobs-20260831-132400-google"]
        reset = self.obs["resobs-20260831-142100-google-reset"]
        with self.assertRaises(ValueError):
            self.manager.calculate_five_hour_delta(before, reset)


if __name__ == "__main__":
    unittest.main()
