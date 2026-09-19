import json
import uuid
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

class InvoiceGenerator:
    INVOICE_DIR = Path("events/invoices")
    
    @classmethod
    def setup(cls):
        cls.INVOICE_DIR.mkdir(parents=True, exist_ok=True)
        
    @classmethod
    def generate_invoice(cls, experiment_data: dict, customer_email: str, customer_name: str) -> dict:
        cls.setup()
        
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=7)
        
        prospect_id = experiment_data.get("prospect_alias", "UNKNOWN-PROSPECT")
        amount = experiment_data.get("price_eur", 0.0)
        target_offering = experiment_data.get("target_offering", "UNKNOWN-OFFERING")
        
        # Generate stable but unique references
        date_str = now.strftime("%Y%m%d")
        invoice_seq = len(list(cls.INVOICE_DIR.glob(f"*{prospect_id}*"))) + 1
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
            "autonomous_spend_eur": 0.0
        }
        
        out_path = cls.INVOICE_DIR / f"{invoice_id}.json"
        with open(out_path, "w") as f:
            json.dump(invoice_doc, f, indent=2)
            
        print(f"Generated Invoice: {invoice_id} for {amount} EUR")
        print(f"File: {out_path}")
        return invoice_doc

if __name__ == "__main__":
    # Test Run
    test_experiment = {
        "prospect_alias": "P-AUDIT-02",
        "price_eur": 99.0,
        "target_offering": "REV-OPP-B2B-AUTONOMY-AUDIT"
    }
    InvoiceGenerator.generate_invoice(test_experiment, "lead@example.com", "Test Lead")
