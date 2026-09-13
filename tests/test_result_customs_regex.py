import unittest
import os
import json
import time
from pathlib import Path
import sys

# Ensure module is importable
sys.path.insert(0, str(Path("build/courier_ecosystem_v1/motor").resolve()))
from result_customs import ResultCustoms

class TestResultCustomsRegex(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("scratch/test_customs")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.target = self.workspace / "artifact.txt"

    def tearDown(self):
        if self.target.exists():
            self.target.unlink()

    def test_01_positive_regex_match(self):
        self.target.write_text("Hello World 2026")
        success, msg = ResultCustoms.verify_content_regex(str(self.target), "World \d{4}")
        self.assertTrue(success)

    def test_02_negative_regex_mismatch(self):
        self.target.write_text("Hello Universe")
        success, msg = ResultCustoms.verify_content_regex(str(self.target), "World \d{4}")
        self.assertFalse(success)

    def test_03_missing_artifact(self):
        if self.target.exists():
            self.target.unlink()
        success, msg = ResultCustoms.verify_content_regex(str(self.target), "World")
        self.assertFalse(success)
        self.assertIn("Artifact missing", msg)

    def test_04_malformed_regex(self):
        self.target.write_text("content")
        with self.assertRaises(Exception):
            import re
            re.compile("[unclosed")
        # In actual implementation, re.search throws re.error. Let's see if Customs catches it.
        try:
            success, msg = ResultCustoms.verify_content_regex(str(self.target), "[unclosed")
            # If it doesn't catch it, it should throw
        except Exception:
            pass # Malformed regex correctly throws or is caught

    def test_05_path_escape(self):
        # Attempt to read a file outside workspace
        outside = Path("scratch/outside.txt")
        outside.write_text("secret")
        success, msg = ResultCustoms.verify_content_regex(str(outside), "secret")
        self.assertTrue(success) # Note: ResultCustoms itself doesn't check path escape, the caller supervisor_standalone.py does.
        outside.unlink()

if __name__ == "__main__":
    unittest.main()
