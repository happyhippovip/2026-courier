"""Privacy precheck, pilot price hypothesis, and a prospect reading that does not contact."""

from courier_runtime.revenue import (
    Job,
    Lead,
    LeadError,
    PriceHypothesis,
    assess_prospect,
    pilot_price_hypothesis,
    privacy_gaps,
    self_funding,
)
from courier_runtime.revenue_store import RevenueStore

import pytest

PRIVACY = {
    "data": "task text the user selected",
    "storage": "local ledger on the user machine",
    "providers": "none",
    "permissions": "read the selected task only",
    "retention": "until the user deletes the ledger",
    "deletion": "delete the ledger file",
}


def _lead():
    lead = Lead("L1", "Example Studio", "CI stays red after restart", "public repo issue 12")
    lead.privacy = dict(PRIVACY)
    return lead


def test_missing_privacy_answer_blocks_qualification():
    lead = Lead("L1", "Example Studio", "CI stays red", "public issue")
    with pytest.raises(LeadError, match="privacy"):
        lead.move("QUALIFIED", 1)
    assert lead.state == "PROSPECT"
    assert lead.history == []
    partial = dict(PRIVACY)
    del partial["deletion"]
    lead.privacy = partial
    with pytest.raises(LeadError, match="deletion"):
        lead.move("QUALIFIED", 1)
    assert privacy_gaps({"data": "mail them at pilot@example.com", **{k: PRIVACY[k] for k in PRIVACY if k != "data"}})


def test_contact_address_is_not_a_privacy_answer():
    answers = dict(PRIVACY)
    answers["storage"] = "send the file to pilot@example.com"
    gaps = privacy_gaps(answers)
    assert any("contact address" in gap for gap in gaps)
    assert privacy_gaps({**PRIVACY, "email": "pilot@example.com"})
    lead = _lead()
    lead.privacy = answers
    with pytest.raises(LeadError, match="contact address"):
        lead.move("QUALIFIED", 1)
    assert lead.state == "PROSPECT"


def test_hypothesis_is_not_revenue():
    hypothesis = pilot_price_hypothesis()
    assert isinstance(hypothesis, PriceHypothesis)
    assert (hypothesis.low_eur, hypothesis.high_eur) == (49.0, 99.0)
    guessed = Job("J", "A", "pilot", 79, paid=True, delivered=True, price_kind="hypothesis")
    assert guessed.revenue_eur == 0.0
    assert self_funding([guessed], 183)["paid_revenue_eur"] == 0
    confirmed = Job("J2", "A", "pilot", 79, paid=True, delivered=True)
    assert confirmed.revenue_eur == 79
    other = PriceHypothesis("other", 10.0, 20.0)
    refused = assess_prospect(_lead(), other)
    assert refused["fit"] == "refused"
    assert refused["contacted"] is False


def test_prospect_assessment_does_not_contact_and_survives_reload(tmp_path):
    lead = _lead()
    first = assess_prospect(lead, pilot_price_hypothesis())
    assert first["fit"] == "ready"
    assert first["contacted"] is False
    assert first["state"] == "PROSPECT"
    assert first["price"] == "hypothesis, not a charge"
    assert "http" not in first["price"]
    assert lead.state == "PROSPECT" and lead.history == []
    store = RevenueStore(tmp_path)
    store.save_lead(lead)
    loaded = store.leads()[0]
    second = assess_prospect(loaded, pilot_price_hypothesis())
    assert second == first
    assert loaded.state == "PROSPECT" and loaded.history == []
    again = assess_prospect(store.leads()[0], pilot_price_hypothesis())
    assert again == second


def test_assessment_refuses_a_contact_shaped_organisation():
    lead = _lead()
    lead.organisation = "pilot@example.com"
    report = assess_prospect(lead, pilot_price_hypothesis())
    assert report["fit"] == "refused"
    assert report["contacted"] is False
    assert lead.state == "PROSPECT"
