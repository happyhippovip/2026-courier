from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.inbound_response_observer as iro
from scripts.inbound_response_observer import (
    InboundResponseObserver,
    ResponseClassification,
)


def test_classify_message_text():
    obs = InboundResponseObserver()

    cls, conf = obs.classify_message_text("Delivery status", "Mailer-Daemon undeliverable")
    assert cls == ResponseClassification.BOUNCE
    assert conf > 0.9

    cls, conf = obs.classify_message_text("Re: Audit", "I am out of office until Monday")
    assert cls == ResponseClassification.AUTO_REPLY

    cls, conf = obs.classify_message_text("Re: Update", "Please unsubscribe and remove me")
    assert cls == ResponseClassification.UNSUBSCRIBE_OR_STOP

    cls, conf = obs.classify_message_text("Re: Hello", "You reached the wrong person here")
    assert cls == ResponseClassification.WRONG_PERSON

    cls, conf = obs.classify_message_text("Re: Audit", "No thanks, we will pass on this")
    assert cls == ResponseClassification.NOT_INTERESTED

    cls, conf = obs.classify_message_text("Re: Pricing", "This is too expensive for our budget")
    assert cls == ResponseClassification.PRICE_OBJECTION

    cls, conf = obs.classify_message_text("Re: Offer", "Please send invoice so we can proceed")
    assert cls == ResponseClassification.POSITIVE_INTEREST

    cls, conf = obs.classify_message_text("Re: Offer", "How does it work and what is the timeline?")
    assert cls == ResponseClassification.QUESTION

    cls, conf = obs.classify_message_text("Hello", "Just wanted to say hello")
    assert cls == ResponseClassification.UNKNOWN


def test_process_inbound_message_positive_interest(tmp_path: Path):
    obs = InboundResponseObserver(repo_dir=tmp_path)
    exp_dir = tmp_path / "events" / "revenue-opportunities" / "market_intelligence"
    exp_dir.mkdir(parents=True, exist_ok=True)
    exp_file = exp_dir / "exp_123.json"
    exp_file.write_text(json.dumps({"id": "exp_123", "target": "Acme Corp"}), encoding="utf-8")

    mock_gen = MagicMock()
    mock_gen.generate_invoice.return_value = {"invoice_id": "INV-12345"}

    with patch.object(iro, "InvoiceGenerator", mock_gen):
        res = obs.process_inbound_message(
            experiment_id="exp_123",
            subject="Let's proceed",
            body="Please send invoice right away",
            sender_email="prospect@example.com",
        )
        assert res["classification"] == ResponseClassification.POSITIVE_INTEREST.value
        assert res["action_taken"] == "INVOICE_GENERATED"
        assert res["invoice_id"] == "INV-12345"


def test_process_inbound_message_fallback_invoice(tmp_path: Path):
    obs = InboundResponseObserver(repo_dir=tmp_path)
    exp_dir = tmp_path / "events" / "revenue-opportunities" / "market_intelligence"
    exp_dir.mkdir(parents=True, exist_ok=True)
    exp_file = exp_dir / "exp_456.json"
    exp_file.write_text(json.dumps({"id": "exp_456"}), encoding="utf-8")

    with patch.object(iro, "InvoiceGenerator", None):
        res = obs.process_inbound_message(
            experiment_id="exp_456",
            subject="Proceed",
            body="Please send invoice please",
            sender_email="prospect@example.com",
        )
        assert res["action_taken"] == "SIMULATED_INVOICE_GENERATED"
        assert "INV-SIM" in res["invoice_id"]


def test_process_inbound_message_missing_experiment(tmp_path: Path):
    obs = InboundResponseObserver(repo_dir=tmp_path)
    res = obs.process_inbound_message(
        experiment_id="exp_missing",
        subject="Proceed",
        body="Please send invoice please",
        sender_email="prospect@example.com",
    )
    assert res["action_taken"] == "ERROR_EXPERIMENT_NOT_FOUND"


def test_main_cli_mock_reply(tmp_path: Path, capsys):
    code = iro.main(["--mock-reply", "exp_test", "--repo-dir", str(tmp_path), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["experiment_id"] == "exp_test"
