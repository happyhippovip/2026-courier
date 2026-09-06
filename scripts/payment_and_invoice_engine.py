#!/usr/bin/env python3
"""Payment and Invoice Generation Engine for Autonomous Money Machine.

Provides zero-spend commercial billing, invoice generation, payment link formatting,
and grounded payment verification for B2B Autonomy Audit (€99) and Content Transformation (€49).

Payment Destination State:
- PAYMENT_DESTINATION_SETUP_REQUIRED: When payment_destination_config.json is unconfigured.
- REAL_PAYMENT_DESTINATION_VERIFIED: When valid Stripe Link or IBAN details are configured.

Payment Receipt State:
- MANUAL_BANK_EVIDENCE_REQUIRED: Verified bank transaction ID must be confirmed by account owner.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from money_machine_pipeline import MoneyMachinePipeline, OpportunityState


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class PaymentAndInvoiceEngine:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.invoices_dir = self.repo_dir / "events" / "invoices"
        self.invoices_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.repo_dir / "events" / "runtime-state" / "payment_destination_config.json"
        self.tx_file = self.repo_dir / "events" / "runtime-state" / "verified_transactions.json"
        self.tx_file.parent.mkdir(parents=True, exist_ok=True)
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def get_payment_destination_status(self) -> Dict[str, Any]:
        """Audits real payment destination configuration state."""
        if not self.config_file.exists():
            return {
                "destination_state": "PAYMENT_DESTINATION_SETUP_REQUIRED",
                "receipt_state": "MANUAL_BANK_EVIDENCE_REQUIRED",
                "canonical_state": "PAYMENT_SETUP_REQUIRED",
                "payment_rails_available": [],
                "is_actionable": False,
                "message": "No real payment rail configured in payment_destination_config.json",
            }

        try:
            cfg = json.loads(self.config_file.read_text(encoding="utf-8"))
            rails = []
            if cfg.get("stripe_payment_link"):
                rails.append("STRIPE_PAYMENT_LINK")
            if cfg.get("iban") and cfg.get("account_holder"):
                rails.append("SEPA_DIRECT_IBAN")
            if cfg.get("paypal_link"):
                rails.append("PAYPAL_ME")

            if not rails:
                return {
                    "destination_state": "PAYMENT_DESTINATION_SETUP_REQUIRED",
                    "receipt_state": "MANUAL_BANK_EVIDENCE_REQUIRED",
                    "canonical_state": "PAYMENT_SETUP_REQUIRED",
                    "payment_rails_available": [],
                    "is_actionable": False,
                    "message": "payment_destination_config.json exists but contains no active payment rails",
                }

            return {
                "destination_state": "REAL_PAYMENT_DESTINATION_VERIFIED",
                "receipt_state": "MANUAL_BANK_EVIDENCE_REQUIRED",
                "canonical_state": "PAYMENT_READY_HUMAN_RECEIPT_VERIFICATION",
                "payment_rails_available": rails,
                "is_actionable": True,
                "business_name": cfg.get("business_name", "2026-Courier"),
            }
        except Exception as e:
            return {
                "destination_state": "PAYMENT_DESTINATION_SETUP_REQUIRED",
                "receipt_state": "MANUAL_BANK_EVIDENCE_REQUIRED",
                "canonical_state": "PAYMENT_SETUP_REQUIRED",
                "error": str(e),
                "is_actionable": False,
            }

    def generate_invoice(
        self,
        opportunity_id: str,
        prospect_id: str,
        amount_eur: float,
        customer_name: str,
        customer_email: str,
    ) -> Dict[str, Any]:
        """Generates a canonical structured invoice embedding real payment instructions if configured."""
        dest_status = self.get_payment_destination_status()
        date_str = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
        invoice_id = f"INV-{prospect_id}-{date_str}-01"
        payment_ref = f"REF-{invoice_id}-{hashlib.sha256(f'{invoice_id}{customer_email}'.encode('utf-8')).hexdigest()[:8]}"

        cfg = {}
        if self.config_file.exists():
            try:
                cfg = json.loads(self.config_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        payment_method = "SEPA_BANK_TRANSFER"
        payment_link = cfg.get("stripe_payment_link") or cfg.get("paypal_link") or "Awaiting account owner configuration"
        iban_info = cfg.get("iban_masked") or "Awaiting account owner configuration"
        business_name = cfg.get("business_name", "2026-Courier Commercial Operations")

        invoice_data = {
            "invoice_id": invoice_id,
            "opportunity_id": opportunity_id,
            "prospect_id": prospect_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "amount_eur": amount_eur,
            "currency": "EUR",
            "business_name": business_name,
            "payment_reference": payment_ref,
            "payment_link": payment_link,
            "created_at": utc_now(),
            "due_date": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).isoformat(),
            "status": "ISSUED_UNPAID",
            "destination_verified": dest_status["is_actionable"],
            "autonomous_spend_eur": 0.0,
        }

        # Render Markdown Invoice
        md_content = f"""# Commercial Invoice: {invoice_id}
**Issuer:** {business_name}
**Billed To:** {customer_name} ({customer_email})
**Date:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')} | **Due Date:** In 7 Days
**Payment Reference (Required):** `{payment_ref}`

---

### Line Items
| Description | Qty | Unit Price | Total |
| :--- | :---: | :---: | :---: |
| {opportunity_id} (Fixed-Scope Commercial Service) | 1 | €{amount_eur:.2f} | €{amount_eur:.2f} |

**Total Due:** **€{amount_eur:.2f} EUR**

---

### Payment Instructions
- **Payment Reference:** `{payment_ref}` (Must be included in payment reference note)
- **Payment Rail / Link:** {payment_link}
- **Bank Transfer Details:** {iban_info}
- **Turnaround SLA:** Delivery within 24-48 Hours upon verified funds receipt.
"""

        invoice_file = self.invoices_dir / f"{invoice_id}.md"
        invoice_file.write_text(md_content, encoding="utf-8")

        json_file = self.invoices_dir / f"{invoice_id}.json"
        json_file.write_text(json.dumps(invoice_data, indent=2) + "\n", encoding="utf-8")

        return {
            "status": "INVOICE_GENERATED",
            "invoice_id": invoice_id,
            "payment_reference": payment_ref,
            "amount_eur": amount_eur,
            "invoice_file": str(invoice_file.relative_to(self.repo_dir)),
            "destination_verified": dest_status["is_actionable"],
        }

    def verify_payment_and_advance_revenue(
        self,
        invoice_id: str,
        bank_tx_reference: str,
        amount_received_eur: float,
    ) -> Dict[str, Any]:
        """Validates real payment funds receipt and advances canonical ledger to REVENUE_RECEIVED."""
        json_file = self.invoices_dir / f"{invoice_id}.json"
        if not json_file.exists():
            return {"status": "ERROR", "message": f"Invoice {invoice_id} not found"}

        invoice_data = json.loads(json_file.read_text(encoding="utf-8"))
        expected_amount = invoice_data.get("amount_eur", 0.0)

        if amount_received_eur < expected_amount:
            return {
                "status": "PARTIAL_PAYMENT_REJECTED",
                "received": amount_received_eur,
                "expected": expected_amount,
            }

        # Check duplicate transaction reference
        txs = []
        if self.tx_file.exists():
            try:
                txs = json.loads(self.tx_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        if any(t.get("bank_tx_reference") == bank_tx_reference for t in txs):
            return {
                "status": "BLOCKED_DUPLICATE_TRANSACTION",
                "bank_tx_reference": bank_tx_reference,
            }

        # Update invoice
        invoice_data["status"] = "PAID"
        invoice_data["paid_at"] = utc_now()
        invoice_data["bank_tx_reference"] = bank_tx_reference
        invoice_data["amount_received_eur"] = amount_received_eur
        json_file.write_text(json.dumps(invoice_data, indent=2) + "\n", encoding="utf-8")

        # Persist transaction record
        txs.append({
            "tx_id": f"TX-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "invoice_id": invoice_id,
            "opportunity_id": invoice_data.get("opportunity_id"),
            "prospect_id": invoice_data.get("prospect_id"),
            "amount_eur": amount_received_eur,
            "bank_tx_reference": bank_tx_reference,
            "verified_at": utc_now(),
        })
        self.tx_file.write_text(json.dumps(txs, indent=2) + "\n", encoding="utf-8")

        # Advance canonical ledger
        ledger = self.pipeline.load_ledger()
        op_id = invoice_data.get("opportunity_id")
        op = ledger.get(op_id)
        if op:
            op.state = OpportunityState.REVENUE_RECEIVED.value
            op.real_revenue_received_eur += amount_received_eur
            op.evidence_confidence = 1.0
            op.result = f"REVENUE_RECEIVED: Verified €{amount_received_eur:.2f} funds received (TX: {bank_tx_reference}). Ready for delivery."
            ledger[op_id] = op
            self.pipeline.save_ledger(ledger)

        return {
            "status": "REVENUE_VERIFIED",
            "invoice_id": invoice_id,
            "amount_received_eur": amount_received_eur,
            "bank_tx_reference": bank_tx_reference,
            "new_state": OpportunityState.REVENUE_RECEIVED.value,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Payment and Invoice Engine")
    parser.add_argument("--audit", action="store_true", help="Audit payment destination status")
    args = parser.parse_args()

    engine = PaymentAndInvoiceEngine()
    if args.audit:
        res = engine.get_payment_destination_status()
        print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
