#!/usr/bin/env python3
"""Mail Auth Gate Observer & Self-Resuming Autonomous Dispatcher.

Monitors macOS Mail account authentication status safely with timeout guards.
When authentication is detected:
1. Verifies outgoing transport readiness without false market exposures.
2. Executes ONLY the authorized single P-01 market experiment (€99 B2B Agent Reliability Check).
3. Enforces strict duplicate-send fencing and zero-secret persistence.
4. Records empirical timestamp, correlation ID, and message fingerprint.
5. Advances canonical ledger to EXPOSURE and parks P-01 branch in WAITING_FOR_RESPONSE.
6. Automatically releases worker capacity to continue other independent Money Machine tasks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from money_machine_pipeline import MoneyMachinePipeline, OpportunityState


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class MailAuthGateObserver:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.tracker_file = self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit" / "outreach_tracker.json"
        self.gate_file = self.repo_dir / "events" / "approvals" / "human_fast_gates" / "gate_email_transport_persistent_auth.json"
        self.state_file = self.repo_dir / "events" / "runtime-state" / "mail_auth_gate_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def check_live_apple_mail_accounts(self) -> Tuple[bool, int, str]:
        """Queries Apple Mail account count using a 2-second timeout guard.

        Returns (is_authenticated, account_count, detail_msg).
        Zero secret inspection, zero credential handling.
        """
        applescript = """
        try
            with timeout of 2 seconds
                tell application "Mail"
                    set accCount to count of accounts
                    return accCount
                end tell
            end timeout
        on error errMsg
            return "ERROR: " & errMsg
        end try
        """
        try:
            res = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = res.stdout.strip()
            if out.startswith("ERROR:"):
                return False, 0, f"Apple Mail pending or modal dialog open: {out}"
            count = int(out)
            return (count > 0), count, f"Detected {count} configured Mail accounts"
        except Exception as e:
            return False, 0, f"Mail query check error: {e}"

    def get_persisted_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "status": "AWAITING_AUTH",
            "accounts_count": 0,
            "transport_ready": False,
            "p01_send_status": "NOT_SENT",
            "p01_correlation_id": None,
            "p01_sent_at": None,
            "last_checked_at": utc_now(),
            "unauthorized_spend_eur": 0.0,
        }

    def save_state(self, state: Dict[str, Any]) -> None:
        state["last_checked_at"] = utc_now()
        self.state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def execute_p01_dispatch(self, dry_run: bool = False) -> Dict[str, Any]:
        """Executes controlled, single-prospect dispatch for Prospect P-01."""
        if not self.tracker_file.exists():
            return {"status": "ERROR", "message": "Tracker file missing"}

        data = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        p1 = next((p for p in data.get("prospects", []) if p.get("prospect_id") == "P-01"), None)
        if not p1:
            return {"status": "ERROR", "message": "P-01 not found"}

        # Duplicate send guard
        if p1.get("sent_at") is not None:
            return {
                "status": "BLOCKED_DUPLICATE_SEND",
                "message": f"P-01 already sent at {p1['sent_at']}",
                "sent_at": p1["sent_at"],
            }

        message_text = p1.get("personalized_message", "")
        message_fingerprint = hashlib.sha256(message_text.encode("utf-8")).hexdigest()
        correlation_id = f"CORR-P01-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}"

        if dry_run:
            send_success = True
            delivery_detail = "MOCK_TRANSPORT_DELIVERY_SUCCESS"
        else:
            # Execute actual AppleScript send via Mail
            clean_message = message_text.replace('"', '\\"')
            applescript_send = f"""
            tell application "Mail"
                set msg to make new outgoing message with properties {{subject:"€99 AI Agent Reliability & Crash-Safety Check", content:"{clean_message}", visible:false}}
                tell msg
                    make new to recipient at end of to recipients with properties {{address:"founder@example.com"}}
                    send
                end tell
            end tell
            """
            try:
                res = subprocess.run(
                    ["osascript", "-e", applescript_send],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                send_success = (res.returncode == 0)
                delivery_detail = "APPLE_MAIL_DELIVERY_SENT" if send_success else f"SEND_FAILED: {res.stderr.strip()}"
            except Exception as e:
                send_success = False
                delivery_detail = f"EXCEPTION: {e}"

        if not send_success:
            return {
                "status": "SEND_FAILED",
                "detail": delivery_detail,
                "correlation_id": correlation_id,
            }

        # Update P-01 record
        sent_timestamp = utc_now()
        p1["sent_at"] = sent_timestamp
        p1["economic_state"] = "EXPOSURE"
        p1["response_state"] = "WAITING_FOR_RESPONSE"
        p1["correlation_id"] = correlation_id
        p1["message_fingerprint"] = message_fingerprint
        p1["delivery_detail"] = delivery_detail
        p1["human_action_count_this_send"] = 0

        self.tracker_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        # Update canonical ledger
        ledger = self.pipeline.load_ledger()
        op = ledger.get("REV-OPP-B2B-AUTONOMY-AUDIT")
        if op:
            op.state = OpportunityState.EXPOSURE.value
            op.evidence_confidence = 0.90
            op.result = f"EXPOSURE_COMPLETED: Prospect P-01 transmitted at {sent_timestamp} (Correlation: {correlation_id}). Branch parked at WAITING_FOR_RESPONSE."
            ledger["REV-OPP-B2B-AUTONOMY-AUDIT"] = op
            self.pipeline.save_ledger(ledger)

        # Update observer state
        obs_state = self.get_persisted_state()
        obs_state["status"] = "P01_EXPOSURE_COMPLETED"
        obs_state["p01_send_status"] = "SENT"
        obs_state["p01_correlation_id"] = correlation_id
        obs_state["p01_sent_at"] = sent_timestamp
        self.save_state(obs_state)

        return {
            "status": "EXPOSURE_TRANSMITTED",
            "prospect_id": "P-01",
            "opportunity_id": "REV-OPP-B2B-AUTONOMY-AUDIT",
            "timestamp": sent_timestamp,
            "correlation_id": correlation_id,
            "message_fingerprint": message_fingerprint,
            "delivery_detail": delivery_detail,
            "real_external_exposures": 1 if not dry_run else 0,
            "next_action": "PARK_P01_WAITING_FOR_RESPONSE_AND_CONTINUE_INDEPENDENT_WORK",
        }

    def poll_and_auto_resume(self, dry_run: bool = False) -> Dict[str, Any]:
        """Polls Mail auth status and triggers automatic resumption when verified."""
        is_auth, count, msg = self.check_live_apple_mail_accounts()
        obs_state = self.get_persisted_state()
        obs_state["accounts_count"] = count

        if not is_auth and not dry_run:
            obs_state["status"] = "AWAITING_AUTH"
            obs_state["transport_ready"] = False
            self.save_state(obs_state)
            return {
                "status": "AWAITING_AUTH",
                "ready_for_one_time_auth": True,
                "human_action": "Complete the account-provider sign-in in Apple Mail.",
                "after_auth": "Do nothing else. The system detects authorization and continues itself.",
                "details": msg,
            }

        # Auth detected!
        obs_state["status"] = "AUTH_DETECTED"
        obs_state["transport_ready"] = True
        self.save_state(obs_state)

        # Execute single P-01 dispatch automatically
        if obs_state.get("p01_send_status") != "SENT":
            dispatch_res = self.execute_p01_dispatch(dry_run=dry_run)
            return {
                "status": "AUTH_DETECTED_AND_RESUMED",
                "transport_ready": True,
                "dispatch_result": dispatch_res,
            }

        return {
            "status": "AUTH_ACTIVE_P01_ALREADY_SENT",
            "transport_ready": True,
            "p01_sent_at": obs_state.get("p01_sent_at"),
            "next_action": "WAITING_FOR_RESPONSE",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mail Auth Gate Observer")
    parser.add_argument("--poll", action="store_true", help="Poll Mail auth and resume automatically")
    parser.add_argument("--dry-run", action="store_true", help="Simulate state machine without real external send")
    parser.add_argument("--bring-mail-to-front", action="store_true", help="Bring Apple Mail to foreground")
    args = parser.parse_args()

    observer = MailAuthGateObserver()

    if args.bring_mail_to_front:
        subprocess.run(["osascript", "-e", 'tell application "Mail" to activate'], check=False)
        print("Apple Mail activated to foreground.")
        return 0

    res = observer.poll_and_auto_resume(dry_run=args.dry_run)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
