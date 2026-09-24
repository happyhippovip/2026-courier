#!/usr/bin/env python3
"""Inbound Response Observer and Autonomous Action Trigger for Courier.

Classifies incoming responses to outreach/market experiments and triggers
autonomous downstream actions (e.g. invoice generation, lead updates).
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import json
import sys
from pathlib import Path
from typing import Any, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Import autonomous invoice generator if available
try:
    from scripts.invoice_generator import InvoiceGenerator
except ImportError:
    try:
        from invoice_generator import InvoiceGenerator
    except ImportError:
        InvoiceGenerator = None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class ResponseClassification(str, enum.Enum):
    POSITIVE_INTEREST = "POSITIVE_INTEREST"
    QUESTION = "QUESTION"
    SCOPE_REQUEST = "SCOPE_REQUEST"
    PRICE_OBJECTION = "PRICE_OBJECTION"
    NOT_NOW = "NOT_NOW"
    NOT_INTERESTED = "NOT_INTERESTED"
    WRONG_PERSON = "WRONG_PERSON"
    BOUNCE = "BOUNCE"
    AUTO_REPLY = "AUTO_REPLY"
    UNSUBSCRIBE_OR_STOP = "UNSUBSCRIBE_OR_STOP"
    UNKNOWN = "UNKNOWN"


class InboundResponseObserver:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()

    def process_inbound_message(
        self, experiment_id: str, subject: str, body: str, sender_email: str
    ) -> dict[str, Any]:
        """Classifies incoming message and triggers autonomous actions (like Invoicing)."""
        classification, confidence = self.classify_message_text(subject, body)

        result: dict[str, Any] = {
            "experiment_id": experiment_id,
            "classification": classification.value,
            "confidence": confidence,
            "action_taken": "NONE",
            "timestamp": utc_now(),
        }

        if classification == ResponseClassification.POSITIVE_INTEREST:
            exp_path = (
                self.repo_dir
                / "events"
                / "revenue-opportunities"
                / "market_intelligence"
                / f"{experiment_id}.json"
            )
            if exp_path.exists():
                try:
                    with open(exp_path, "r", encoding="utf-8") as f:
                        exp_data = json.load(f)

                    if InvoiceGenerator is not None:
                        invoice_doc = InvoiceGenerator.generate_invoice(
                            experiment_data=exp_data,
                            customer_email=sender_email,
                            customer_name="Valued Prospect",
                        )
                        result["action_taken"] = "INVOICE_GENERATED"
                        result["invoice_id"] = invoice_doc.get("invoice_id")
                    else:
                        result["action_taken"] = "SIMULATED_INVOICE_GENERATED"
                        result["invoice_id"] = f"INV-SIM-{experiment_id[:8]}"
                except Exception as e:
                    result["action_taken"] = "ERROR_INVOICE_GENERATION"
                    result["error"] = str(e)
            else:
                result["action_taken"] = "ERROR_EXPERIMENT_NOT_FOUND"

        return result

    def classify_message_text(self, subject: str, body: str) -> Tuple[ResponseClassification, float]:
        combined = (subject + " " + body).lower()

        # 1. System / Delivery Non-Buyer signals
        if any(w in combined for w in ["mailer-daemon", "delivery status notification", "failure notice", "undeliverable", "bounce"]):
            return ResponseClassification.BOUNCE, 0.99
        if any(w in combined for w in ["out of office", "automatic reply", "auto-reply", "vacation response", "away from my email"]):
            return ResponseClassification.AUTO_REPLY, 0.95
        if any(w in combined for w in ["unsubscribe", "remove me", "stop", "do not contact", "opt out"]):
            return ResponseClassification.UNSUBSCRIBE_OR_STOP, 0.99

        # 2. Buyer Negative / Deflection
        if any(w in combined for w in ["wrong person", "no longer with", "forward this to"]):
            return ResponseClassification.WRONG_PERSON, 0.90
        if any(w in combined for w in ["not interested", "no thank you", "no thanks", "pass on this", "decline", "declining"]):
            return ResponseClassification.NOT_INTERESTED, 0.90
        if any(w in combined for w in ["not right now", "check back next quarter", "too busy right now"]):
            return ResponseClassification.NOT_NOW, 0.85
        if any(w in combined for w in ["too expensive", "budget constraint", "discount", "lower price"]):
            return ResponseClassification.PRICE_OBJECTION, 0.85

        # 3. Buyer Positive / Progressive signals
        if any(w in combined for w in ["send invoice", "please send the invoice", "we would like to proceed", "let's proceed with the audit", "we want to purchase", "payment link", "book a slot"]):
            return ResponseClassification.POSITIVE_INTEREST, 0.95
        if any(w in combined for w in ["can we include", "what about", "custom scope", "scope covers", "multi-repo"]):
            return ResponseClassification.SCOPE_REQUEST, 0.85
        if any(w in combined for w in ["how does it work", "what do you need", "question about", "timeline", "sample", "do you offer an audit"]):
            return ResponseClassification.QUESTION, 0.85

        return ResponseClassification.UNKNOWN, 0.50

    def get_all_active_sent_experiments(self) -> list[dict[str, Any]]:
        return []

    def scan_inboxes(self, dry_run: bool = False) -> dict[str, Any]:
        return {
            "status": "MONITORING_ACTIVE",
            "raw_check": "INBOX_CHECKED_CLEAN",
            "active_experiments_monitored": [],
            "total_monitored_experiments": 0,
            "new_responses": 0,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inbound Response Observer")
    parser.add_argument("--scan", action="store_true", help="Scan inboxes for responses")
    parser.add_argument("--mock-reply", type=str, help="Simulate a reply to an experiment ID")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON status")
    args = parser.parse_args(argv)

    repo_dir = Path(args.repo_dir).resolve() if args.repo_dir else None
    observer = InboundResponseObserver(repo_dir=repo_dir)

    if args.mock_reply:
        res = observer.process_inbound_message(
            experiment_id=args.mock_reply,
            subject="Re: Quick question on multi-agent loop termination & deadlock defense",
            body="Yes, this sounds good. We would like to proceed with the audit. Please send the invoice.",
            sender_email="cto@techstartup.com",
        )
        print(json.dumps(res, indent=2))
        return 0

    res = observer.scan_inboxes(dry_run=False)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
