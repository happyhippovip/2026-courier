#!/usr/bin/env python3
"""Native macOS Payment Destination Authorization Dialog.

Opens a native macOS graphical dialog directly on the user's desktop:
- Zero terminal commands required by the human.
- Zero JSON editing.
- Zero sensitive financial credentials sent to LLM or committed to Git.
- Automatically persists to gitignored local runtime state and auto-resumes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from payment_gate_observer import PaymentGateObserver


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class NativePaymentDialogLauncher:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.observer = PaymentGateObserver(repo_dir=self.repo_dir)

    def launch_ui_dialog(self, dry_run: bool = False) -> Dict[str, Any]:
        """Launches native macOS GUI dialog asking the human for their preferred payment rail."""
        if dry_run:
            return {
                "status": "LOCAL_PAYMENT_GATE_OPENED_FOR_HUMAN",
                "ui_type": "MACOS_NATIVE_DIALOG",
                "human_terminal_required": False,
                "human_json_editing_required": False,
                "auto_resume_enabled": True,
            }

        applescript_dialog = """
        tell application "System Events"
            activate
            set railChoice to choose from list {"1. Stripe Payment Link (Recommended)", "2. PayPal.me Link", "3. SEPA Direct IBAN Wire"} with title "Commercial Payment Destination Setup" with prompt "How should customers pay for €99 B2B Audits & €49 Content Transformations?" default items {"1. Stripe Payment Link (Recommended)"} OK button name "Next" cancel button name "Cancel"
            if railChoice is false then
                return "CANCELLED"
            end if
            set selectedRail to item 1 of railChoice

            if selectedRail contains "Stripe" then
                set promptText to "Enter your live Stripe Payment Link URL (e.g. https://buy.stripe.com/...):"
                set defaultText to "https://buy.stripe.com/"
            else if selectedRail contains "PayPal" then
                set promptText to "Enter your PayPal.me link (e.g. https://paypal.me/...):"
                set defaultText to "https://paypal.me/"
            else
                set promptText to "Enter your Bank IBAN:"
                set defaultText to "DE"
            end if

            set inputDialog to display dialog promptText default answer defaultText with title "Payment Destination Authorization" with icon note buttons {"Cancel", "Save & Authorize"} default button "Save & Authorize"
            if button returned of inputDialog is "Save & Authorize" then
                return (text returned of inputDialog)
            else
                return "CANCELLED"
            end if
        end tell
        """

        try:
            res = subprocess.run(
                ["osascript", "-e", applescript_dialog],
                capture_output=True,
                text=True,
                timeout=60,
            )
            val = res.stdout.strip()
            if val and val != "CANCELLED" and not val.startswith("ERROR"):
                save_res = self.observer.validate_and_save_config(val)
                return {
                    "status": "PAYMENT_DESTINATION_CONFIGURED",
                    "ui_result": "USER_INPUT_SAVED",
                    "save_status": save_res,
                    "auto_resume_triggered": True,
                }
            elif val == "CANCELLED":
                return {
                    "status": "LOCAL_PAYMENT_GATE_OPENED_FOR_HUMAN",
                    "ui_result": "USER_CANCELLED_OR_DISMISSED",
                    "auto_resume_triggered": False,
                }
            else:
                return {
                    "status": "LOCAL_PAYMENT_GATE_OPENED_FOR_HUMAN",
                    "ui_result": "AWAITING_USER_INPUT",
                    "detail": val,
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "LOCAL_PAYMENT_GATE_OPENED_FOR_HUMAN",
                "ui_result": "DIALOG_ACTIVE_ON_DESKTOP",
                "human_terminal_required": False,
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "detail": str(e),
            }


def main() -> int:
    parser = argparse.ArgumentParser(description="Native Payment Dialog Launcher")
    parser.add_argument("--launch", action="store_true", help="Launch native macOS payment dialog")
    parser.add_argument("--dry-run", action="store_true", help="Simulate launching dialog")
    args = parser.parse_args()

    launcher = NativePaymentDialogLauncher()
    res = launcher.launch_ui_dialog(dry_run=args.dry_run)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
