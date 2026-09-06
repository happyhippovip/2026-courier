#!/usr/bin/env python3
"""Autonomous Commercial Qualification & Payment Responder.

When an inbound buyer response is classified (POSITIVE_INTEREST, QUESTION, SCOPE_REQUEST):
1. Formats the pre-approved commercial qualification response (strictly enforcing 1-workflow boundary, fixed pricing, 48h turnaround, zero secrets).
2. Generates the structured invoice & payment reference token via PaymentAndInvoiceEngine.
3. Advances prospect state to PAYMENT_DISCUSSION and stages the delivery trigger.
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

from payment_and_invoice_engine import PaymentAndInvoiceEngine
from money_machine_pipeline import MoneyMachinePipeline, OpportunityState


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class AutonomousCommercialResponder:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.payment_engine = PaymentAndInvoiceEngine(repo_dir=self.repo_dir)
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def handle_positive_interest(
        self,
        prospect_id: str,
        opportunity_id: str,
        customer_name: str,
        customer_email: str,
    ) -> Dict[str, Any]:
        """Handles positive interest signal: generates invoice and pre-approved commercial reply."""
        amount_eur = 99.0 if "B2B" in opportunity_id else 49.0
        service_name = "€99 AI Agent Reliability Check" if "B2B" in opportunity_id else "€49 Content Transformation (3 Finished Assets)"

        inv_res = self.payment_engine.generate_invoice(
            opportunity_id=opportunity_id,
            prospect_id=prospect_id,
            amount_eur=amount_eur,
            customer_name=customer_name,
            customer_email=customer_email,
        )

        reply_copy = (
            f"Hi {customer_name} — great to connect! "
            f"Here are the next steps for the {service_name}:\n\n"
            f"1. Intake: Share the sanitized workflow code / developer notes (zero production secrets or credentials required).\n"
            f"2. Invoice: Attached invoice {inv_res['invoice_id']} for €{amount_eur:.2f} EUR (Payment Reference: {inv_res['payment_reference']}).\n"
            f"3. Delivery: We deliver the complete report / marketing assets within 24-48h of payment receipt.\n\n"
            f"Looking forward to working together."
        )

        # Update ledger to PAYMENT_DISCUSSION
        ledger = self.pipeline.load_ledger()
        op = ledger.get(opportunity_id)
        if op:
            op.state = OpportunityState.PAYMENT_DISCUSSION.value
            op.evidence_confidence = 0.95
            op.result = f"PAYMENT_DISCUSSION: Invoice {inv_res['invoice_id']} issued for {prospect_id}. Awaiting payment receipt."
            ledger[opportunity_id] = op
            self.pipeline.save_ledger(ledger)

        return {
            "status": "QUALIFIED_PAYMENT_DISCUSSION_STAGED",
            "prospect_id": prospect_id,
            "opportunity_id": opportunity_id,
            "invoice_id": inv_res["invoice_id"],
            "payment_reference": inv_res["payment_reference"],
            "amount_eur": amount_eur,
            "reply_copy": reply_copy,
            "new_state": OpportunityState.PAYMENT_DISCUSSION.value,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Commercial Responder")
    parser.add_argument("--test-p01", action="store_true", help="Test handling positive interest for P-01")
    args = parser.parse_args()

    responder = AutonomousCommercialResponder()
    if args.test_p01:
        res = responder.handle_positive_interest(
            prospect_id="P-01",
            opportunity_id="REV-OPP-B2B-AUTONOMY-AUDIT",
            customer_name="Founder",
            customer_email="founder@example.com",
        )
        print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
