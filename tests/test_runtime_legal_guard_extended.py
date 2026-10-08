import pytest
from courier_runtime.legal_guard import check_outward

def test_legal_guard_all_brands_detected():
    brands = [
        "binance", "coinbase", "kraken", "metamask", "trust wallet",
        "bybit", "okx", "bitpanda", "trezor", "ledger live", "ledger nano"
    ]
    for brand in brands:
        msg = f"We are fully interoperable with {brand.upper()} integrations."
        problems = check_outward(msg, "reply", human_approval="lead-appr")
        assert any("third-party brand named" in p and brand in p.lower() for p in problems), f"Failed for {brand}"

def test_legal_guard_all_secret_patterns_detected():
    secrets = [
        "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz",
        "gho_" + "1234567890abcdefghijklmnopqrstuvwxyz",
        "ghs_" + "1234567890abcdefghijklmnopqrstuvwxyz",
        "ghu_" + "1234567890abcdefghijklmnopqrstuvwxyz",
        "AKIA" + "0123456789ABCDEF",
        "-----BEGIN RSA PRIVATE KEY-----",
        "sk-" + "abcdef0123456789abcdef0123456789",
        "0x" + "a" * 64,
    ]
    for sec in secrets:
        msg = f"Check this raw string: {sec} found in logs."
        problems = check_outward(msg, "reply", human_approval="lead-appr")
        assert any("secret-shaped value" in p for p in problems), f"Failed for secret: {sec}"

def test_legal_guard_german_absolute_claims():
    claims = [
        "Wir bieten das weltweit beste System.",
        "Das ist das größte Netzwerk überhaupt.",
        "Unsere Software ist garantiert absturzsicher.",
        "Die Plattform ist unhackbar.",
        "Wir sind die Nummer 1 in der Region.",
        "Wir sind Nummer eins beim Datenschutz."
    ]
    for claim in claims:
        problems = check_outward(claim, "reply", human_approval="lead-appr")
        assert any("absolute claim" in p for p in problems), f"Failed for claim: {claim}"

def test_legal_guard_fear_urgency_triggers():
    fears = [
        "Bitte sofort handeln!",
        "Das ist Ihre letzte Chance vor dem Freeze.",
        "Ihr Konto ist in Gefahr!",
        "Handeln Sie, bevor es zu spät ist!",
        "Sehr dringend, bitte umgehende Rückmeldung.",
        "Your wallet is at risk right now."
    ]
    for fear in fears:
        problems = check_outward(fear, "reply", human_approval="lead-appr")
        assert any("fear or urgency wording" in p for p in problems), f"Failed for fear: {fear}"

def test_legal_guard_pitch_keywords_in_security_notice():
    pitch_keywords = ["€", "EUR", "preis", "price", "angebot", "offer", "kaufen", "buy"]
    for word in pitch_keywords:
        msg = f"Notice: line 44 has missing hash. Unser Preis beträgt 50 {word}."
        problems = check_outward(msg, "security_contact", human_approval="lead-appr")
        assert any("first security notice must not contain a sales offer" in p for p in problems), f"Failed for pitch word: {word}"

def test_legal_guard_legal_advice_english_and_german():
    legal_texts = [
        "Das ist keine Rechtsberatung, aber ihr seid nach § 14 rechtlich haftbar.",
        "You are legally liable under current directives.",
        "You are liable for any damages."
    ]
    for lt in legal_texts:
        problems = check_outward(lt, "reply", human_approval="lead-appr")
        assert any("reads as legal advice" in p for p in problems), f"Failed for: {lt}"

def test_legal_guard_multiple_violations_aggregated():
    bad_msg = (
        "Sofort handeln! Wir sind die beste der welt. Ihr Metamask key "
        "sk-" + "a"*32 + " ist geleakt. Kaufen Sie jetzt unser Angebot für 99 EUR."
    )
    problems = check_outward(bad_msg, "security_contact", finding_is_secret=True)
    # Missing human approval, fear, absolute claim, brand, secret, sales offer
    assert any("needs a human approval" in p for p in problems)
    assert any("fear or urgency" in p for p in problems)
    assert any("absolute claim" in p for p in problems)
    assert any("third-party brand" in p for p in problems)
    assert any("secret-shaped value" in p for p in problems)
    assert any("sales offer" in p for p in problems)
