import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


class InvoiceGenerator:
    INVOICE_DIR = Path("events/invoices")

    @classmethod
    def setup(cls, repo_dir: str | Path | None = None) -> Path:
        if repo_dir:
            cls.INVOICE_DIR = Path(repo_dir) / "events" / "invoices"
        else:
            root = Path(__file__).resolve().parent.parent
            cls.INVOICE_DIR = root / "events" / "invoices"
        cls.INVOICE_DIR.mkdir(parents=True, exist_ok=True)
        return cls.INVOICE_DIR

    @classmethod
    def generate_invoice(
        cls,
        experiment_data: dict,
        customer_email: str,
        customer_name: str,
        repo_dir: str | Path | None = None,
        dry_run: bool = False,
        quiet: bool = False,
    ) -> dict:
        invoice_dir = cls.setup(repo_dir)

        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=7)

        prospect_id = experiment_data.get("prospect_alias", "UNKNOWN-PROSPECT")
        amount = float(experiment_data.get("price_eur", 0.0))
        target_offering = experiment_data.get("target_offering", "UNKNOWN-OFFERING")

        # Generate stable but unique references
        date_str = now.strftime("%Y%m%d")
        invoice_seq = len(list(invoice_dir.glob(f"*{prospect_id}*"))) + 1
        invoice_id = f"INV-{prospect_id}-{date_str}-{invoice_seq:02d}"

        ref_uuid = str(uuid.uuid4())[:8]
        payment_ref = f"REF-{invoice_id}-{ref_uuid}"

        invoice_doc = {
            "invoice_id": invoice_id,
            "opportunity_id": target_offering,
            "prospect_id": prospect_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "amount_eur": amount,
            "currency": "EUR",
            "business_name": "2026-Courier Commercial Operations",
            "payment_reference": payment_ref,
            "payment_link": "Awaiting account owner configuration (AUTONOMOUS GENERATION)",
            "created_at": now.isoformat(),
            "due_date": due_date.isoformat(),
            "artifact_status": "DRAFT_SIMULATION",
            "payment_status": "UNCONFIGURED",
            "destination_verified": False,
            "autonomous_spend_eur": 0.0,
        }

        if dry_run:
            if not quiet:
                print(f"[DRY-RUN] Prepared Invoice: {invoice_id} for {amount} EUR")
            return invoice_doc

        out_path = invoice_dir / f"{invoice_id}.json"
        fd, tmp_file = tempfile.mkstemp(dir=invoice_dir, prefix="inv_", suffix=".tmp")
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(invoice_doc, f, indent=2)
        os.replace(tmp_file, out_path)

        if not quiet:
            print(f"Generated Invoice: {invoice_id} for {amount} EUR")
            print(f"File: {out_path}")
        return invoice_doc


def main():
    parser = argparse.ArgumentParser(description="Courier Commercial Invoice Generator")
    parser.add_argument("--prospect-alias", default="P-AUDIT-02", help="Prospect alias ID")
    parser.add_argument("--price-eur", type=float, default=99.0, help="Invoice price in EUR")
    parser.add_argument("--target-offering", default="REV-OPP-B2B-AUTONOMY-AUDIT", help="Offering identifier")
    parser.add_argument("--customer-email", default="lead@example.com", help="Customer email address")
    parser.add_argument("--customer-name", default="Test Lead", help="Customer name")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--dry-run", action="store_true", help="Prepare invoice without writing to disk")
    parser.add_argument("--json", action="store_true", help="Output result JSON to stdout")
    args = parser.parse_args()

    data = {
        "prospect_alias": args.prospect_alias,
        "price_eur": args.price_eur,
        "target_offering": args.target_offering,
    }

    doc = InvoiceGenerator.generate_invoice(
        data,
        customer_email=args.customer_email,
        customer_name=args.customer_name,
        repo_dir=args.repo_dir,
        dry_run=args.dry_run,
        quiet=args.json,
    )
    if args.json:
        print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
