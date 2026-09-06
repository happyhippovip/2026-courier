#!/usr/bin/env python3
"""Test suite for NativePaymentDialogLauncher."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.launch_native_payment_dialog import NativePaymentDialogLauncher


class TestNativePaymentDialogLauncher(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dialog_test_"))
        self.launcher = NativePaymentDialogLauncher(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_launch_ui_dialog_dry_run(self):
        """Dry run verifies non-blocking local GUI presentation with zero terminal and zero JSON editing."""
        res = self.launcher.launch_ui_dialog(dry_run=True)
        self.assertEqual(res["status"], "LOCAL_PAYMENT_GATE_OPENED_FOR_HUMAN")
        self.assertEqual(res["ui_type"], "MACOS_NATIVE_DIALOG")
        self.assertFalse(res["human_terminal_required"])
        self.assertFalse(res["human_json_editing_required"])
        self.assertTrue(res["auto_resume_enabled"])


if __name__ == "__main__":
    unittest.main()
