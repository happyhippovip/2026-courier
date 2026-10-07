import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from scripts.inbound_response_observer import (
    InboundResponseObserver,
    ResponseClassification,
    utc_now,
    main,
)

def test_utc_now():
    now = utc_now()
    assert isinstance(now, str)
    assert "T" in now

def test_classify_message_text_bounce():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("Undeliverable: Hello", "")
    assert c == ResponseClassification.BOUNCE
    assert conf == 0.99

def test_classify_message_text_autoreply():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("Out of office", "")
    assert c == ResponseClassification.AUTO_REPLY
    assert conf == 0.95

def test_classify_message_text_unsubscribe():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("Stop", "remove me from this list")
    assert c == ResponseClassification.UNSUBSCRIBE_OR_STOP
    assert conf == 0.99

def test_classify_message_text_wrong_person():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("wrong person", "")
    assert c == ResponseClassification.WRONG_PERSON
    assert conf == 0.90

def test_classify_message_text_not_interested():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("not interested", "")
    assert c == ResponseClassification.NOT_INTERESTED
    assert conf == 0.90

def test_classify_message_text_not_now():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("too busy right now", "")
    assert c == ResponseClassification.NOT_NOW
    assert conf == 0.85

def test_classify_message_text_price_objection():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("too expensive", "")
    assert c == ResponseClassification.PRICE_OBJECTION
    assert conf == 0.85

def test_classify_message_text_positive():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("please send the invoice", "")
    assert c == ResponseClassification.POSITIVE_INTEREST
    assert conf == 0.95

def test_classify_message_text_scope():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("what about", "multi-repo")
    assert c == ResponseClassification.SCOPE_REQUEST
    assert conf == 0.85

def test_classify_message_text_question():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("how does it work", "")
    assert c == ResponseClassification.QUESTION
    assert conf == 0.85

def test_classify_message_text_unknown():
    observer = InboundResponseObserver()
    c, conf = observer.classify_message_text("random words", "here")
    assert c == ResponseClassification.UNKNOWN
    assert conf == 0.50

def test_process_inbound_message_not_positive(tmp_path):
    observer = InboundResponseObserver(repo_dir=tmp_path)
    res = observer.process_inbound_message("exp1", "not interested", "", "test@test.com")
    assert res["classification"] == ResponseClassification.NOT_INTERESTED
    assert res["action_taken"] == "NONE"

def test_process_inbound_message_positive_no_experiment(tmp_path):
    observer = InboundResponseObserver(repo_dir=tmp_path)
    res = observer.process_inbound_message("exp1", "send invoice", "", "test@test.com")
    assert res["classification"] == ResponseClassification.POSITIVE_INTEREST
    assert res["action_taken"] == "ERROR_EXPERIMENT_NOT_FOUND"

def test_process_inbound_message_positive_invoice_error(tmp_path, monkeypatch):
    observer = InboundResponseObserver(repo_dir=tmp_path)
    exp_dir = tmp_path / "events" / "revenue-opportunities" / "market_intelligence"
    exp_dir.mkdir(parents=True)
    exp_file = exp_dir / "exp1.json"
    exp_file.write_text(json.dumps({"price": 1000}))

    # Explicitly mock InvoiceGenerator to raise an error
    class MockErrorInvoiceGenerator:
        @staticmethod
        def generate_invoice(*args, **kwargs):
            raise ValueError("Test error")
            
    import scripts.inbound_response_observer
    monkeypatch.setattr(scripts.inbound_response_observer, "InvoiceGenerator", MockErrorInvoiceGenerator, raising=False)

    res = observer.process_inbound_message("exp1", "send invoice", "", "test@test.com")
    assert res["classification"] == ResponseClassification.POSITIVE_INTEREST
    assert res["action_taken"] == "ERROR_INVOICE_GENERATION"
    assert "error" in res

def test_process_inbound_message_positive_invoice_success(tmp_path, monkeypatch):
    observer = InboundResponseObserver(repo_dir=tmp_path)
    exp_dir = tmp_path / "events" / "revenue-opportunities" / "market_intelligence"
    exp_dir.mkdir(parents=True)
    exp_file = exp_dir / "exp1.json"
    exp_file.write_text(json.dumps({"price": 1000}))

    # Inject mock InvoiceGenerator
    class MockInvoiceGenerator:
        @staticmethod
        def generate_invoice(*args, **kwargs):
            return {"invoice_id": "INV-123"}
            
    import scripts.inbound_response_observer
    monkeypatch.setattr(scripts.inbound_response_observer, "InvoiceGenerator", MockInvoiceGenerator, raising=False)

    res = observer.process_inbound_message("exp1", "send invoice", "", "test@test.com")
    assert res["classification"] == ResponseClassification.POSITIVE_INTEREST
    assert res["action_taken"] == "INVOICE_GENERATED"
    assert res["invoice_id"] == "INV-123"

def test_get_all_active_sent_experiments():
    observer = InboundResponseObserver()
    assert observer.get_all_active_sent_experiments() == []

def test_scan_inboxes():
    observer = InboundResponseObserver()
    res = observer.scan_inboxes()
    assert res["status"] == "MONITORING_ACTIVE"

def test_main_scan(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["inbound_response_observer.py", "--scan"])
    assert main() == 0
    out, _ = capsys.readouterr()
    assert "MONITORING_ACTIVE" in out

def test_main_mock_reply(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["inbound_response_observer.py", "--mock-reply", "EXP123"])
    assert main() == 0
    out, _ = capsys.readouterr()
    assert "Simulating inbound reply for EXP123..." in out
    assert "POSITIVE_INTEREST" in out
