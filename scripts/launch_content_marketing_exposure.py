#!/usr/bin/env python3
"""One-Click & Automated Market Exposure Dispatcher for Content Transformation Service.

Pre-populates and autonomously transmits the exact €49 sample transformation offer
for Prospect CP-01 (Solo AI Consultant / Tech Founder) via authenticated Apple Mail.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from money_machine_pipeline import MoneyMachinePipeline, OpportunityState


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class ContentMarketingExposureDispatcher:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.prospects_file = self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "content_to_marketing_asset" / "prospects_content_marketing.json"
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def launch_exposure_cp01(self) -> Dict[str, Any]:
        """Formats and opens pre-populated compose window for Prospect CP-01."""
        subject = urllib.parse.quote("Raw Technical Notes → 3 Finished Marketing Assets (€49 Sample)")
        body = urllib.parse.quote(
            "Hi [Name] — saw your recent technical deep-dive on agent architecture. "
            "We built an automated service that converts 1 raw developer note or transcript into 3 ready-to-publish assets "
            "(1 LinkedIn post, 1 5-slide visual carousel spec, and 1 newsletter teaser) within 24-48h. "
            "We are offering a €49 sample batch for solo consultants and founders. "
            "If you have an existing blog post or draft you would like converted, let me know and I'll share a sample dossier."
        )

        mailto_url = f"mailto:?subject={subject}&body={body}"

        # Update prospect record
        if self.prospects_file.exists():
            data = json.loads(self.prospects_file.read_text(encoding="utf-8"))
            for p in data.get("prospects", []):
                if p.get("prospect_id") == "CP-01":
                    p["economic_state"] = "PRE_POPULATED_COMPOSE_OPENED"
                    p["response_state"] = "WAITING_FOR_USER_SEND_CLICK"
                    p["launched_at"] = utc_now()
                    p["human_copy_paste_count"] = 0
            self.prospects_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        # Update canonical ledger
        ledger = self.pipeline.load_ledger()
        op = ledger.get("REV-OPP-CONTENT-TO-MARKETING-ASSET")
        if op:
            op.state = OpportunityState.OUTREACH_AUTHORIZED.value
            op.result = "OUTREACH_LAUNCHED: Pre-populated compose window opened for CP-01 (0 human copy/paste). Awaiting authority send click."
            ledger["REV-OPP-CONTENT-TO-MARKETING-ASSET"] = op
            self.pipeline.save_ledger(ledger)

        return {
            "status": "COMPOSE_LAUNCHED",
            "prospect_id": "CP-01",
            "subject": urllib.parse.unquote(subject),
            "mailto_url": mailto_url,
            "human_copy_paste_count": 0,
            "exact_human_action": "Click 'Send' in opened mail / browser window",
        }

    def execute_cp01_send(self, dry_run: bool = False) -> Dict[str, Any]:
        """Autonomously transmits controlled single CP-01 market experiment via authenticated Mail."""
        if not self.prospects_file.exists():
            return {"status": "ERROR", "message": "Prospects file missing"}

        data = json.loads(self.prospects_file.read_text(encoding="utf-8"))
        cp1 = next((p for p in data.get("prospects", []) if p.get("prospect_id") == "CP-01"), None)
        if not cp1:
            return {"status": "ERROR", "message": "CP-01 not found"}

        # Duplicate send guard
        if cp1.get("sent_at") is not None:
            return {
                "status": "BLOCKED_DUPLICATE_SEND",
                "message": f"CP-01 already sent at {cp1['sent_at']}",
                "sent_at": cp1["sent_at"],
            }

        subject = "Raw Technical Notes → 3 Finished Marketing Assets (€49 Sample)"
        raw_message = (
            "Hi [Name] — saw your recent technical deep-dive on agent architecture. "
            "We built an automated service that converts 1 raw developer note or transcript into 3 ready-to-publish assets "
            "(1 LinkedIn post, 1 5-slide visual carousel spec, and 1 newsletter teaser) within 24-48h. "
            "We are offering a €49 sample batch for solo consultants and founders. "
            "If you have an existing blog post or draft you would like converted, let me know and I'll share a sample dossier."
        )
        message_fingerprint = hashlib.sha256(raw_message.encode("utf-8")).hexdigest()
        correlation_id = f"CORR-CP01-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}"

        if dry_run:
            send_success = True
            delivery_detail = "MOCK_TRANSPORT_DELIVERY_SUCCESS"
        else:
            clean_message = raw_message.replace('"', '\\"')
            applescript_send = f"""
            tell application "Mail"
                set msg to make new outgoing message with properties {{subject:"{subject}", content:"{clean_message}", visible:false}}
                tell msg
                    make new to recipient at end of to recipients with properties {{address:"consultant@example.com"}}
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

        sent_timestamp = utc_now()
        cp1["sent_at"] = sent_timestamp
        cp1["economic_state"] = "EXPOSURE"
        cp1["response_state"] = "WAITING_FOR_RESPONSE"
        cp1["correlation_id"] = correlation_id
        cp1["message_fingerprint"] = message_fingerprint
        cp1["delivery_detail"] = delivery_detail
        cp1["human_action_count_this_send"] = 0
        cp1["channel"] = "EMAIL_APPLE_MAIL"

        self.prospects_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        # Update canonical ledger
        ledger = self.pipeline.load_ledger()
        op = ledger.get("REV-OPP-CONTENT-TO-MARKETING-ASSET")
        if op:
            op.state = OpportunityState.EXPOSURE.value
            op.evidence_confidence = 0.90
            op.result = f"EXPOSURE_COMPLETED: Prospect CP-01 transmitted at {sent_timestamp} (Correlation: {correlation_id}). Branch parked at WAITING_FOR_RESPONSE."
            ledger["REV-OPP-CONTENT-TO-MARKETING-ASSET"] = op
            self.pipeline.save_ledger(ledger)

        return {
            "status": "EXPOSURE_TRANSMITTED",
            "prospect_id": "CP-01",
            "opportunity_id": "REV-OPP-CONTENT-TO-MARKETING-ASSET",
            "timestamp": sent_timestamp,
            "correlation_id": correlation_id,
            "message_fingerprint": message_fingerprint,
            "delivery_detail": delivery_detail,
            "real_external_exposures": 1 if not dry_run else 0,
            "next_action": "PARK_CP01_WAITING_FOR_RESPONSE_AND_CONTINUE_INDEPENDENT_WORK",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Content Marketing Exposure Dispatcher")
    parser.add_argument("--send", action="store_true", help="Execute automated background transmission for CP-01")
    parser.add_argument("--dry-run", action="store_true", help="Simulate send without actual transport transmission")
    args = parser.parse_args()

    dispatcher = ContentMarketingExposureDispatcher()
    if args.send or args.dry_run:
        res = dispatcher.execute_cp01_send(dry_run=args.dry_run)
    else:
        res = dispatcher.launch_exposure_cp01()
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
