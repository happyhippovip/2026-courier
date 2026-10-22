"""A missing worker_status must not be stamped as a passing verification."""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import revenue_v1_safety_baseline as rvsb


class TestMissingWorkerStatus(unittest.TestCase):
    def test_missing_or_boolean_worker_status_is_rejected(self):
        accepted = {"verdict": "PASS", "accepted": True, "reasons": [], "verifier": {"name": "x"}}
        with TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            for status in (None, True, "PASS "):
                candidate = {"report_json_sha256": "h1"}
                if status is not None:
                    candidate["worker_status"] = status
                with patch("revenue_v1_safety_baseline.run_independent_verifier", return_value=accepted):
                    with self.assertRaises(SystemExit) as caught:
                        rvsb.verify({}, candidate, work_dir)
                self.assertIn("worker_status", str(caught.exception))
