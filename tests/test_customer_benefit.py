"""The homepage states the customer benefit in one plain sentence."""

from pathlib import Path

import pytest

from scripts.customer_benefit import BenefitError, check_benefit, check_page


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "website" / "src" / "index.html"
PUBLIC = ROOT / "website" / "public" / "index.html"

PLAIN = (
    '<p id="kundennutzen">Sie bekommen einen schriftlichen Prüfbericht zum festen Preis. '
    "Ein Mensch liest den Bericht, bevor er geliefert wird.</p>"
)


def test_plain_sentence_passes_and_jargon_fails():
    assert check_benefit(PLAIN) == []
    jargon = PLAIN.replace("Prüfbericht", "Verifier-Journal")
    reasons = check_benefit(jargon)
    assert any("internal word" in reason for reason in reasons)
    assert check_benefit("<p>kein Satz</p>") == ["missing kundennutzen"]
    with pytest.raises(BenefitError):
        check_page(Path("/tmp/courier-no-such-benefit.html"), strict=True)


def test_homepage_states_the_benefit_once():
    report = check_page(INDEX)
    assert report["ok"] is True, report
    assert report["text"].count("Prüfbericht") == 1
    again = check_page(INDEX)
    assert again == report
    public = check_page(PUBLIC)
    assert public["text"] == report["text"]
    assert public["ok"] is True
