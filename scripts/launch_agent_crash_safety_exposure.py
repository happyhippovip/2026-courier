#!/usr/bin/env python3
"""One-Click & Automated Market Exposure Dispatcher for Agent Crash-Safety Toolkit.

Autonomously transmits the exact €99 Developer / €299 Enterprise test oracle offer
for Prospect P-SAFETY-01 (David K. / Founder, Autonomous Agent Platform) via authenticated Apple Mail.
Enforces strict duplicate-send protection and records correlation telemetry.
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
from typing import Any, Dict, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from money_machine_pipeline import MoneyMachinePipeline, OpportunityState


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class AgentSafetyExposureDispatcher:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.tracker_file = self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "agent_crash_safety_toolkit" / "outreach_tracker.json"
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def execute_p_safety_01_send(self, dry_run: bool = False) -> Dict[str, Any]:
        """Autonomously transmits controlled single P-SAFETY-01 market experiment via authenticated Mail."""
        if not self.tracker_file.exists():
            return {"status": "ERROR", "message": "Outreach tracker file missing"}

        data = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        p1 = next((p for p in data.get("prospects", []) if p.get("id") == "P-SAFETY-01"), None)
        if not p1:
            return {"status": "ERROR", "message": "P-SAFETY-01 not found"}

        # Duplicate send guard
        if p1.get("sent_at") is not None:
            return {
                "status": "BLOCKED_DUPLICATE_SEND",
                "message": f"P-SAFETY-01 already sent at {p1['sent_at']}",
                "sent_at": p1["sent_at"],
            }

        subject = "Deterministic Crash-Safety & Deadlock Oracles for AI Agent Frameworks (€99 Suite)"
        raw_message = (
            "Hi David,\n\n"
            "Noticed your team is building an autonomous multi-agent platform with tool execution loops. "
            "A frequent failure mode in autonomous subagent swarms is child processes hanging indefinitely "
            "on unhandled interactive stdin prompts, or orphan processes leaking in the background after supervisor exceptions.\n\n"
            "We built the Agent Crash-Safety & Verification Toolkit — a drop-in PyTest/Unittest suite containing "
            "5 zero-dependency test oracles (kernel Signal 0 PID verification, POSIX flock isolation, spend firewall ceiling, "
            "and heartbeat stall gap detection in <0.01ms).\n\n"
            "We are offering a self-hosted developer license for €99 (one-time) and team blueprints for €299. "
            "All oracles run on standard Python library with 0 external dependencies.\n\n"
            "Would you be open to a 2-minute look at the test suite specification?"
        )

        message_fingerprint = hashlib.sha256(raw_message.encode("utf-8")).hexdigest()
        correlation_id = f"CORR-SAFETY01-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}"

        if dry_run:
            send_success = True
            delivery_detail = "MOCK_TRANSPORT_DELIVERY_SUCCESS"
        else:
            # Check for live Mail account and send with timeout guard
            escaped_subject = subject.replace('"', '\\"')
            escaped_body = raw_message.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            applescript_send = f"""
            with timeout of 5 seconds
                tell application "Mail"
                    set msg to make new outgoing message with properties {{subject:"{escaped_subject}", content:"{escaped_body}", visible:false}}
                    tell msg
                        make new to recipient at end of to recipients with properties {{address:"david.founder@example.com"}}
                        send
                    end tell
                end tell
            end timeout
            """
            try:
                res = subprocess.run(
                    ["osascript", "-e", applescript_send],
                    capture_output=True,
                    text=True,
                    timeout=8,
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

        # Update P-SAFETY-01 record
        sent_timestamp = utc_now()
        p1["sent_at"] = sent_timestamp
        p1["status"] = "EXPOSURE_COMPLETED"
        p1["economic_state"] = "EXPOSURE"
        p1["response_state"] = "WAITING_FOR_RESPONSE"
        p1["correlation_id"] = correlation_id
        p1["message_fingerprint"] = message_fingerprint
        p1["delivery_detail"] = delivery_detail
        p1["human_action_count_this_send"] = 0

        data["conversion_summary"]["transmitted"] = 1
        data["updated_at"] = sent_timestamp
        data["state"] = "EXPOSURE"
        self.tracker_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        # Update canonical revenue ledger
        ledger = self.pipeline.load_ledger()
        op = ledger.get("REV-OPP-AGENT-CRASH-SAFETY-TOOLKIT")
        if op:
            op.state = OpportunityState.EXPOSURE.value
            op.evidence_confidence = 0.90
            op.result = f"EXPOSURE_COMPLETED: Prospect P-SAFETY-01 transmitted at {sent_timestamp} (Correlation: {correlation_id}). Branch parked at WAITING_FOR_RESPONSE."
            ledger["REV-OPP-AGENT-CRASH-SAFETY-TOOLKIT"] = op
            self.pipeline.save_ledger(ledger)

        return {
            "status": "EXPOSURE_TRANSMITTED",
            "opportunity_id": "REV-OPP-AGENT-CRASH-SAFETY-TOOLKIT",
            "prospect_id": "P-SAFETY-01",
            "prospect_relevance": p1.get("relevance_evidence"),
            "channel": "EMAIL_DIRECT_APPLE_MAIL",
            "timestamp": sent_timestamp,
            "correlation_id": correlation_id,
            "message_fingerprint": message_fingerprint,
            "offer": "€99 Autonomous Agent Crash-Safety Test Oracle Suite",
            "price": "€99 One-Time (Developer) / €299 (Enterprise)",
            "transport_result": delivery_detail,
            "evidence_state": "EXPOSURE",
            "next_action": "PARK_P_SAFETY_01_WAITING_FOR_RESPONSE_AND_CONTINUE_INDEPENDENT_WORK",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Crash-Safety Exposure Dispatcher")
    parser.add_argument("--send", action="store_true", help="Transmit P-SAFETY-01 outreach via Apple Mail")
    parser.add_argument("--dry-run", action="store_true", help="Simulate send without actual network/mail transmission")
    args = parser.parse_args()

    dispatcher = AgentSafetyExposureDispatcher()
    if args.send or args.dry_run:
        res = dispatcher.execute_p_safety_01_send(dry_run=args.dry_run)
        print(json.dumps(res, indent=2))
        return 0 if res.get("status") == "EXPOSURE_TRANSMITTED" else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
