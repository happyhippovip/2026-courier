#!/usr/bin/env python3
"""One-Click Market Exposure Launcher.

Constructs pre-populated, URL-encoded dispatch links for qualified prospects
and launches the user's authenticated default browser or email client directly.

Eliminates manual human copy/pasting:
- Google formats, targets, and pre-populates the entire message.
- Human action is reduced strictly to the final authority click ("Click Send").
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
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


class OneClickMarketExposureLauncher:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.tracker_file = self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "b2b_autonomy_audit" / "outreach_tracker.json"
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def prepare_one_click_url(self, prospect_id: str = "P-01") -> Dict[str, Any]:
        """Prepares pre-populated URL and dispatch parameters for a prospect."""
        if not self.tracker_file.exists():
            return {"status": "ERROR", "message": "Tracker file not found"}

        data = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        prospects = data.get("prospects", [])

        prospect = next((p for p in prospects if p.get("prospect_id") == prospect_id), None)
        if not prospect:
            return {"status": "ERROR", "message": f"Prospect {prospect_id} not found"}

        message_text = prospect.get("personalized_message", "")
        encoded_body = urllib.parse.quote(message_text)
        subject = urllib.parse.quote("€99 AI Agent Reliability & Crash-Safety Check")

        # 1. Primary: mailto URI with subject and full body pre-filled
        mailto_url = f"mailto:founder@example.com?subject={subject}&body={encoded_body}"

        # 2. Web fallback: LinkedIn messaging search URL
        linkedin_url = f"https://www.linkedin.com/search/results/all/?keywords={urllib.parse.quote('AI Coding Agent Founder')}"

        return {
            "status": "PREPARED",
            "prospect_id": prospect_id,
            "target_type": prospect.get("target_type"),
            "channel": prospect.get("channel"),
            "raw_message": message_text,
            "mailto_url": mailto_url,
            "web_url": linkedin_url,
            "human_copy_paste_required": 0,
            "exact_human_action": "Click 'Send' in pre-populated browser / email compose window",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare One-Click Market Exposure")
    parser.add_argument("--prospect", type=str, default="P-01", help="Target prospect ID")
    args = parser.parse_args()

    launcher = OneClickMarketExposureLauncher()
    res = launcher.prepare_one_click_url(args.prospect)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
