#!/usr/bin/env python3
"""Market Exposure & External Evidence Recorder.

Grounded empirical recorder for market outreach events:
- Records actual external exposures (timestamp, prospect_id, channel, message_version)
- Records genuine responses, price reactions, and payment discussions
- Updates canonical revenue ledger states strictly on verified external evidence
- Invariant: Real revenue remains 0.0 EUR until actual customer funds are received.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
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


class MarketExposureRecorder:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.tracker_file = self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit" / "outreach_tracker.json"
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def record_exposure(
        self,
        prospect_id: str,
        channel: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Records an actual verified external exposure to a prospect."""
        if not self.tracker_file.exists():
            return {"status": "ERROR", "message": "Tracker file not found"}

        data = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        prospects = data.get("prospects", [])

        found = False
        for p in prospects:
            if p.get("prospect_id") == prospect_id:
                p["sent_at"] = utc_now()
                p["channel"] = channel
                p["economic_state"] = OpportunityState.EXPOSURE.value
                p["response_state"] = "AWAITING_EXTERNAL_RESPONSE"
                p["notes"] = notes
                found = True
                break

        if not found:
            return {"status": "ERROR", "message": f"Prospect {prospect_id} not found in tracker"}

        data["prospects"] = prospects
        self.tracker_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        # Update canonical ledger: if at least 1 real exposure exists, state advances to EXPOSURE / MARKET_TESTED
        total_exposures = sum(1 for p in prospects if p.get("sent_at") is not None)
        ledger = self.pipeline.load_ledger()
        op = ledger.get("REV-OPP-B2B-AUTONOMY-AUDIT")
        if op:
            op.state = OpportunityState.EXPOSURE.value
            op.result = f"EXPOSURE_RECORDED: {total_exposures} real external exposures sent. Awaiting market responses."
            ledger["REV-OPP-B2B-AUTONOMY-AUDIT"] = op
            self.pipeline.save_ledger(ledger)

        return {
            "status": "EXPOSURE_RECORDED",
            "prospect_id": prospect_id,
            "channel": channel,
            "total_real_exposures": total_exposures,
            "canonical_state": OpportunityState.EXPOSURE.value,
        }

    def record_response(
        self,
        prospect_id: str,
        response_text: str,
        problem_signal: bool,
        scope_requested: bool,
        payment_discussed: bool,
    ) -> Dict[str, Any]:
        """Records an incoming external market response."""
        if not self.tracker_file.exists():
            return {"status": "ERROR", "message": "Tracker file not found"}

        data = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        prospects = data.get("prospects", [])

        found = False
        for p in prospects:
            if p.get("prospect_id") == prospect_id:
                p["response_state"] = "RESPONSE_RECEIVED"
                p["response_text"] = response_text
                p["problem_signal"] = "CONFIRMED" if problem_signal else "NONE"
                p["scope_request"] = "REQUESTED" if scope_requested else "NONE"
                p["payment_discussion"] = "ACTIVE" if payment_discussed else "NONE"
                if payment_discussed:
                    p["economic_state"] = OpportunityState.PAYMENT_DISCUSSION.value
                elif scope_requested or problem_signal:
                    p["economic_state"] = OpportunityState.QUALIFIED_CONVERSATION.value
                else:
                    p["economic_state"] = OpportunityState.RESPONSE.value
                found = True
                break

        if not found:
            return {"status": "ERROR", "message": f"Prospect {prospect_id} not found in tracker"}

        data["prospects"] = prospects
        self.tracker_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        return {
            "status": "RESPONSE_RECORDED",
            "prospect_id": prospect_id,
            "economic_state": p.get("economic_state"),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Record Market Exposure or Response")
    parser.add_argument("--record-exposure", type=str, help="Prospect ID for exposure (e.g. P-01)")
    parser.add_argument("--channel", type=str, default="LINKEDIN_DM", help="Channel used")
    parser.add_argument("--notes", type=str, default="", help="Execution notes")
    args = parser.parse_args()

    recorder = MarketExposureRecorder()
    if args.record_exposure:
        res = recorder.record_exposure(args.record_exposure, args.channel, args.notes)
        print(json.dumps(res, indent=2))
        return 0 if res["status"] == "EXPOSURE_RECORDED" else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
