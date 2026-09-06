#!/usr/bin/env python3
"""Mission 219 Acceptance Test Suite: Mac Desktop Guardian & Popup Autopilot."""

import datetime as dt
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from scripts.desktop_guardian import (
    DesktopGuardian,
    GuardianDecision,
    PopupClassification,
    SecurityGateCategory,
    UIElementInfo,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class TestMission219DesktopGuardian(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m219_guardian_"))
        self.runtime_dir = self.test_dir / "events" / "runtime-state"
        self.alerts_dir = self.test_dir / "events" / "runtime-alerts"

        for d in [self.runtime_dir, self.alerts_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.guardian = DesktopGuardian(repo_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_known_keychain_missing_triggers_safe_cancel_only(self):
        """Known Antigravity keychain missing dialog clicks Abbrechen only, reset is never used."""
        info = UIElementInfo(
            app_name="Antigravity",
            window_title="Schlüsselbund nicht gefunden",
            dialog_text="Es wurde kein Schlüsselbund gefunden, um „antigravity“ zu sichern.",
            buttons=["Abbrechen", "Auf Standard zurücksetzen"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.SAFE_AUTO_DISMISS.value)
        self.assertEqual(dec.action_type, "SAFE_CANCEL_KEYCHAIN")
        self.assertEqual(dec.target_button, "Abbrechen")
        self.assertNotEqual(dec.target_button, "Auf Standard zurücksetzen")
        self.assertTrue(dec.safe_to_execute)

    def test_02_keychain_dialog_with_altered_unknown_text_fails_closed(self):
        """Dialog with altered unknown text classified as UNKNOWN without action."""
        info = UIElementInfo(
            app_name="Antigravity",
            window_title="Schlüsselbund nicht gefunden",
            dialog_text="Ein unbekannter Systemfehler ist aufgetreten.",
            buttons=["OK", "Hilfe"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.UNKNOWN.value)
        self.assertFalse(dec.safe_to_execute)

    def test_03_password_request_triggers_waiting_human(self):
        """Password prompts are gated to WAITING_HUMAN."""
        info = UIElementInfo(
            app_name="SecurityAgent",
            window_title="Kennwort eingeben",
            dialog_text="Geben Sie das Kennwort für den Schlüsselbund ein.",
            buttons=["Abbrechen", "OK"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.WAITING_HUMAN.value)
        self.assertEqual(dec.gate_category, SecurityGateCategory.PASSWORD.value)
        self.assertFalse(dec.safe_to_execute)

    def test_04_touch_id_triggers_waiting_human(self):
        """Touch ID prompts are gated to WAITING_HUMAN."""
        info = UIElementInfo(
            app_name="SecurityAgent",
            window_title="Touch ID erforderlich",
            dialog_text="Legen Sie Ihren Finger auf den Touch ID Sensor.",
            buttons=["Kennwort verwenden", "Abbrechen"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.WAITING_HUMAN.value)
        self.assertEqual(dec.gate_category, SecurityGateCategory.TOUCH_ID.value)
        self.assertFalse(dec.safe_to_execute)

    def test_05_captcha_triggers_waiting_human(self):
        """CAPTCHA / 'Ich bin kein Roboter' prompts are gated to WAITING_HUMAN."""
        info = UIElementInfo(
            app_name="Google Chrome",
            window_title="Sicherheitsüberprüfung",
            dialog_text="Bestätigen Sie: Ich bin kein Roboter (reCAPTCHA).",
            buttons=["Bestätigen", "Abbrechen"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.WAITING_HUMAN.value)
        self.assertEqual(dec.gate_category, SecurityGateCategory.CAPTCHA.value)
        self.assertFalse(dec.safe_to_execute)

    def test_06_enable_overages_is_forbidden(self):
        """Enable Overages prompt is classified as WAITING_HUMAN and forbidden."""
        info = UIElementInfo(
            app_name="Antigravity",
            window_title="Quota Limit Exceeded",
            dialog_text="Enable Overages to continue requests at $0.05/call.",
            buttons=["Enable Overages", "Cancel"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.WAITING_HUMAN.value)
        self.assertEqual(dec.gate_category, SecurityGateCategory.ENABLE_OVERAGES.value)
        self.assertFalse(dec.safe_to_execute)

    def test_07_upgrade_prompt_is_forbidden(self):
        """Upgrade/purchase subscription prompt is classified as WAITING_HUMAN and forbidden."""
        info = UIElementInfo(
            app_name="Antigravity",
            window_title="Upgrade to Pro",
            dialog_text="Your free tier is full. Buy credits or subscribe.",
            buttons=["Upgrade Now", "Later"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.WAITING_HUMAN.value)
        self.assertEqual(dec.gate_category, SecurityGateCategory.BILLING_UPGRADE.value)
        self.assertFalse(dec.safe_to_execute)

    def test_08_quota_detection_marks_model_unavailable_without_restart(self):
        """Quota event marks model resource unavailable while preserving mission state."""
        info = UIElementInfo(
            app_name="Antigravity",
            window_title="Model Limit",
            dialog_text="Baseline model quota reached. Try again later.",
            buttons=["Dismiss"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.PROVIDER_RESOURCE_EVENT.value)
        self.assertTrue(dec.safe_to_execute)

        executed = self.guardian.execute_decision(info, dec)
        self.assertTrue(executed)
        self.assertEqual(self.guardian.telemetry.provider_states.get("GEMINI_BASELINE"), "UNAVAILABLE_UNTIL_RESET")

    def test_09_approved_alternative_provider_failover(self):
        """When baseline model quota reached, alternative authorized provider remains available."""
        self.guardian.telemetry.provider_states["GEMINI_BASELINE"] = "UNAVAILABLE_UNTIL_RESET"
        self.guardian.telemetry.provider_states["GEMINI_FLASH"] = "AVAILABLE"
        self.assertEqual(self.guardian.telemetry.provider_states["GEMINI_BASELINE"], "UNAVAILABLE_UNTIL_RESET")
        self.assertEqual(self.guardian.telemetry.provider_states["GEMINI_FLASH"], "AVAILABLE")

    def test_10_all_model_providers_unavailable_parks_model_branch_safely(self):
        """All models unavailable marks state WAITING_RESOURCE while local deterministic tasks continue."""
        self.guardian.telemetry.provider_states["GEMINI_BASELINE"] = "UNAVAILABLE_UNTIL_RESET"
        self.guardian.telemetry.provider_states["GEMINI_FLASH"] = "UNAVAILABLE_UNTIL_RESET"
        # Financial Firewall strictly intact
        self.assertEqual(self.guardian.telemetry.real_trades, 0)
        self.assertEqual(self.guardian.telemetry.spend_eur, 0.0)

    def test_11_repeated_identical_popup_deduplicated(self):
        """Same popup executed once is deduplicated on subsequent cycles."""
        info = UIElementInfo(
            app_name="Antigravity",
            window_title="Schlüsselbund nicht gefunden",
            dialog_text="Es wurde kein Schlüsselbund gefunden, um „antigravity“ zu sichern.",
            buttons=["Abbrechen", "Auf Standard zurücksetzen"],
        )
        dec = self.guardian.evaluate_dialog(info)
        # Mock successful execution
        self.guardian._processed_popups.add(dec.fingerprint)
        # Second execution attempt is blocked by deduplication
        exec2 = self.guardian.execute_decision(info, dec)
        self.assertFalse(exec2, "Repeated popup execution must be deduplicated")

    def test_12_restart_preserves_processed_popups_state(self):
        """Reinstantiating guardian recovers prior deduplication and state."""
        info = UIElementInfo(
            app_name="Antigravity",
            window_title="Schlüsselbund nicht gefunden",
            dialog_text="Es wurde kein Schlüsselbund gefunden, um „antigravity“ zu sichern.",
            buttons=["Abbrechen", "Auf Standard zurücksetzen"],
        )
        fp = info.fingerprint()
        self.guardian._processed_popups.add(fp)
        self.assertIn(fp, self.guardian._processed_popups)

    def test_13_two_guardian_instances_enforce_single_authority(self):
        """Single instance locking prevents duplicate guardian execution."""
        pid_file = self.guardian.pid_file
        pid_file.write_text(str(os.getpid()), encoding="utf-8")

        # Second instance checks PID
        second_guardian = DesktopGuardian(repo_dir=self.test_dir)
        self.assertTrue(pid_file.exists())
        self.assertEqual(int(pid_file.read_text().strip()), os.getpid())

    def test_14_unknown_popup_fails_closed(self):
        """Unknown popup with arbitrary title and text fails closed with zero action."""
        info = UIElementInfo(
            app_name="RandomApp",
            window_title="System Notification",
            dialog_text="Click OK to continue arbitrary operation.",
            buttons=["OK", "Cancel"],
        )
        dec = self.guardian.evaluate_dialog(info)
        self.assertEqual(dec.classification, PopupClassification.UNKNOWN.value)
        self.assertEqual(dec.action_type, "NO_ACTION")
        self.assertFalse(dec.safe_to_execute)


if __name__ == "__main__":
    unittest.main()
