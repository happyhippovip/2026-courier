import pytest
from courier_runtime.legal_guard import check_outward, CHANNELS, BRANDS, SECRETS, ABSOLUTE_CLAIMS, FEAR


def test_channel_registry_exhaustiveness():
    assert "security_contact" in CHANNELS
    assert "reply" in CHANNELS
    assert "existing_customer" in CHANNELS
    assert "cold_email" in CHANNELS
    assert "public_issue" in CHANNELS


def test_multiple_simultaneous_violations():
    # Text with absolute claim, fear, brand, secret, and legal advice
    bad_text = (
        "We are the best in the world. Your wallet is at risk! "
        "Unlike Coinbase, our system is unhackable. "
        "Here is your secret: AKIA1234567890ABCDEF. "
        "Rechtlich seid ihr voll haftbar."
    )
    problems = check_outward(bad_text, "reply", human_approval="approval-123")
    assert any("absolute claim" in p for p in problems)
    assert any("fear or urgency" in p for p in problems)
    assert any("third-party brand" in p for p in problems)
    assert any("secret-shaped" in p for p in problems)
    assert any("legal advice" in p for p in problems)


@pytest.mark.parametrize("brand", BRANDS)
def test_all_prohibited_brands_detected(brand):
    text = f"Notice: we do not endorse {brand} directly."
    problems = check_outward(text, "reply", human_approval="apr-ok")
    assert any("third-party brand named" in p for p in problems)


def test_aws_secret_key_pattern():
    text = "Found AWS access key AKIAIOSFODNN7EXAMPLE in repository."
    problems = check_outward(text, "reply", human_approval="apr-ok")
    assert any("secret-shaped value" in p for p in problems)


def test_private_key_pem_pattern():
    text = "Key: -----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."
    problems = check_outward(text, "reply", human_approval="apr-ok")
    assert any("secret-shaped value" in p for p in problems)


def test_openai_sk_key_pattern():
    text = "Found token: sk-" + "1234567890abcdef1234567890abcdef"
    problems = check_outward(text, "reply", human_approval="apr-ok")
    assert any("secret-shaped value" in p for p in problems)


def test_eth_private_key_pattern():
    text = "Found Ethereum private key: 0x" + "a" * 64
    problems = check_outward(text, "reply", human_approval="apr-ok")
    assert any("secret-shaped value" in p for p in problems)


def test_existing_customer_allows_pitch_with_approval():
    text = "Here is our quarterly update: the service upgrade costs 500 EUR."
    problems = check_outward(text, "existing_customer", human_approval="mgr-approved")
    # Existing customer channel does not forbid sales pitches
    assert problems == []


def test_pitch_in_public_issue_blocked():
    text = "Check out our pricing: buy now for 99 €."
    problems = check_outward(text, "public_issue", human_approval="admin")
    assert any("sales offer" in p for p in problems)


def test_unapproved_always_blocked_even_with_perfect_copy():
    perfect_text = "Clean factual notice regarding system state."
    problems = check_outward(perfect_text, "reply", human_approval=None)
    assert problems == ["needs a human approval id before sending"]
