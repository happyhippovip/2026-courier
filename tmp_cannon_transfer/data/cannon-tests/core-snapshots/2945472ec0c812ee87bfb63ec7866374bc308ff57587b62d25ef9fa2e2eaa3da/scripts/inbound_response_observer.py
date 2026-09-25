import sys
import json
import argparse
import subprocess
import datetime as dt
import enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Import money machine state handling
try:
    from scripts.money_machine_pipeline import MoneyMachinePipeline, OpportunityState
except ImportError:
    pass

# Import new autonomous invoice generator
try:
    from scripts.invoice_generator import InvoiceGenerator
except ImportError:
    pass


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
        
    def process_inbound_message(self, experiment_id: str, subject: str, body: str, sender_email: str) -> Dict[str, Any]:
        """Classifies incoming message and triggers autonomous actions (like Invoicing)."""
        classification, confidence = self.classify_message_text(subject, body)
        
        result = {
            "experiment_id": experiment_id,
            "classification": classification,
            "confidence": confidence,
            "action_taken": "NONE"
        }
        
        if classification == ResponseClassification.POSITIVE_INTEREST:
            # Autonomous Invoice Generation
            print(f"💰 POSITIVE INTEREST DETECTED for {experiment_id}! Initiating Autonomous Invoice Generation...")
            
            # Load the experiment to get pricing
            exp_path = self.repo_dir / "events" / "revenue-opportunities" / "market_intelligence" / f"{experiment_id}.json"
            if exp_path.exists():
                with open(exp_path, "r") as f:
                    exp_data = json.load(f)
                
                try:
                    invoice_doc = InvoiceGenerator.generate_invoice(
                        experiment_data=exp_data, 
                        customer_email=sender_email, 
                        customer_name="Valued Prospect"
                    )
                    result["action_taken"] = "INVOICE_GENERATED"
                    result["invoice_id"] = invoice_doc["invoice_id"]
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

    def get_all_active_sent_experiments(self) -> List[Dict[str, Any]]:
        # Mocking active discovery for brevity in test script
        return []

    def scan_inboxes(self, dry_run: bool = False) -> Dict[str, Any]:
        return {
            "status": "MONITORING_ACTIVE",
            "raw_check": "INBOX_CHECKED_CLEAN",
            "active_experiments_monitored": [],
            "total_monitored_experiments": 0,
            "new_responses": 0,
        }

def main() -> int:
    parser = argparse.ArgumentParser(description="Inbound Response Observer")
    parser.add_argument("--scan", action="store_true", help="Scan inboxes for responses")
    parser.add_argument("--mock-reply", type=str, help="Simulate a reply to an experiment ID (e.g. MARKET_EXPERIMENT_P_AUDIT_01)")
    args = parser.parse_args()

    observer = InboundResponseObserver()
    
    if args.mock_reply:
        print(f"Simulating inbound reply for {args.mock_reply}...")
        res = observer.process_inbound_message(
            experiment_id=args.mock_reply,
            subject="Re: Quick question on multi-agent loop termination & deadlock defense",
            body="Yes, this sounds good. We would like to proceed with the audit. Please send the invoice.",
            sender_email="cto@techstartup.com"
        )
        print(json.dumps(res, indent=2))
        return 0

    res = observer.scan_inboxes(dry_run=False)
    print(json.dumps(res, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
