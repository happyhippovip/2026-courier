import pytest

from courier_runtime.legal_guard import check_outward

CALM_NOTICE = ("Hi, while reading your public repository I noticed that your CI downloads an install script "
               "and runs it without a checksum (.github/workflows/ci.yml, line 12). Pinning a version and checking "
               "its hash closes this. Happy to explain if useful.")


def test_calm_private_notice_with_approval_passes():
    assert check_outward(CALM_NOTICE, "security_contact", human_approval="dennis-ok-1") == []


@pytest.mark.parametrize("text, expected", [
    ("Courier is the best in the world for crypto security.", "absolute claim"),
    ("Wir sind der größte Schutz der Welt.", "absolute claim"),
    ("100% secure, guaranteed.", "absolute claim"),
    ("Your funds are at risk - act now!", "fear"),
    ("Like Binance, we protect you.", "third-party brand"),
    ("Your key ghp_" + "Ab3" * 12 + " is exposed.", "secret-shaped"),
    ("Rechtlich gesehen seid ihr haftbar.", "legal advice"),
])
def test_risky_wording_is_blocked(text, expected):
    problems = check_outward(text, "reply", human_approval="ok")
    assert any(expected in p for p in problems), problems


def test_channel_rules():
    assert any("unsolicited" in p for p in check_outward(CALM_NOTICE, "cold_email", human_approval="ok"))
    assert any("privately" in p for p in check_outward(CALM_NOTICE, "public_issue", True, human_approval="ok"))
    pitch = CALM_NOTICE + " Our repo check costs 149 €."
    assert any("sales offer" in p for p in check_outward(pitch, "security_contact", human_approval="ok"))
    assert check_outward(pitch, "reply", human_approval="ok") == []          # they asked: an offer is fine
    assert check_outward(CALM_NOTICE, "nowhere", human_approval="ok")[0].startswith("unknown channel")


def test_nothing_goes_out_without_a_human():
    assert check_outward(CALM_NOTICE, "security_contact") == ["needs a human approval id before sending"]
