import unittest
from pathlib import Path
from scripts.inbound_response_observer import InboundResponseObserver, ResponseClassification
from scripts.invoice_generator import InvoiceGenerator


class TestM230(unittest.TestCase):
    def setUp(self):
        self.observer = InboundResponseObserver()

    def test_unsubscribe_override(self):
        c, _ = self.observer.classify_message_text("Unsubscribe", "Yes, please remove me from your list.")
        self.assertEqual(c, ResponseClassification.UNSUBSCRIBE_OR_STOP)

    def test_not_interested_override(self):
        c, _ = self.observer.classify_message_text("No thank you", "Do you offer an audit? We are not interested.")
        self.assertEqual(c, ResponseClassification.NOT_INTERESTED)

    def test_question(self):
        c, _ = self.observer.classify_message_text("Quick question", "Do you offer an audit?")
        self.assertEqual(c, ResponseClassification.QUESTION)

    def test_isolated_yes(self):
        c, _ = self.observer.classify_message_text("Update", "Yes")
        self.assertNotEqual(c, ResponseClassification.POSITIVE_INTEREST)

    def test_positive_interest(self):
        c, _ = self.observer.classify_message_text("Proceed", "Please send the invoice for the audit; we'd like to proceed.")
        self.assertEqual(c, ResponseClassification.POSITIVE_INTEREST)

    def test_invoice_semantics(self):
        test_exp = {"prospect_alias": "P-TEST", "price_eur": 99.0, "target_offering": "TEST"}
        inv = InvoiceGenerator.generate_invoice(test_exp, "test@test.com", "Test")
        self.assertEqual(inv["artifact_status"], "DRAFT_SIMULATION")
        self.assertEqual(inv["payment_status"], "UNCONFIGURED")
        self.assertNotIn("status", inv)
        self.assertNotEqual(inv.get("status"), "ISSUED_UNPAID")

        # cleanup
        fpath = Path("events/invoices") / f"{inv['invoice_id']}.json"
        if fpath.exists():
            fpath.unlink()


if __name__ == '__main__':
    unittest.main()
