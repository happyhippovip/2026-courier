import pytest

from courier_runtime.continuation import AcceptedLog
from courier_runtime.spider_slice import ContentStore, ResearchRequest, check_claim


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


# -- spider slice ------------------------------------------------------------------------

PAGE = b"<p>Courier keeps a conclusion supported over time.</p>"


def run_claim(tmp_path, url, quote, fetch):
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    out = check_claim(ResearchRequest("wk-s", url, quote, "https://example.org"), fetch, ContentStore(), log, Clock())
    return out, log


def test_supported_claim_has_byte_anchor_and_ledger_record(tmp_path):
    out, log = run_claim(tmp_path, "https://example.org/p", "conclusion supported",
                         lambda u: (u, PAGE))
    assert out["conclusion"] == "SUPPORTED" and out["anchor"]["offset"] == PAGE.decode().find("conclusion supported")
    assert log.facts()[0].sources[0] == "content:" + out["anchor"]["sha256"]


def test_changed_page_contradicts_and_same_input_same_hash(tmp_path):
    a, _ = run_claim(tmp_path, "https://example.org/p", "not on the page", lambda u: (u, PAGE))
    (tmp_path / "second").mkdir()
    b, _ = run_claim(tmp_path / "second", "https://example.org/p", "not on the page", lambda u: (u, PAGE))
    assert a["conclusion"] == "CONTRADICTED" and a["anchor"]["sha256"] == b["anchor"]["sha256"]


@pytest.mark.parametrize("url, final", [
    ("https://evil.example/p", None), ("http://example.org/p", None),
    ("https://example.org/p", "https://evil.example/landing"),
])
def test_unapproved_origin_or_redirect_is_blocked_and_not_recorded(tmp_path, url, final):
    out, log = run_claim(tmp_path, url, "x", lambda u: (final or u, PAGE))
    assert out["conclusion"] == "BLOCKED" and log.facts() == []


def _reject(tmp_path, quote):
    fetched = []

    def fetch(url):
        fetched.append(url)
        return url, PAGE

    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    out = check_claim(
        ResearchRequest("wk-s", "https://example.org/p", quote, "https://example.org"),
        fetch, ContentStore(), log, Clock(),
    )
    return out, log, fetched


def test_missing_quote_is_rejected_without_fetch_or_ledger(tmp_path):
    out, log, fetched = _reject(tmp_path, None)
    assert out == {"conclusion": "BLOCKED", "reason": "quote is missing"}
    assert fetched == [] and log.facts() == []
    assert AcceptedLog(log.path).facts() == []


def test_empty_quote_is_rejected_without_fetch_or_ledger(tmp_path):
    out, log, fetched = _reject(tmp_path, "")
    assert out == {"conclusion": "BLOCKED", "reason": "empty quote is not a claim"}
    assert fetched == [] and log.facts() == []
    assert AcceptedLog(log.path).facts() == []


def test_lone_surrogate_quote_is_rejected_without_fetch(tmp_path):
    out, log, fetched = _reject(tmp_path, "\ud800")
    assert out == {"conclusion": "BLOCKED", "reason": "quote cannot be encoded as utf-8"}
    assert fetched == [] and log.facts() == []


def test_absent_quote_fact_reloads_with_the_same_statement(tmp_path):
    out, log = run_claim(tmp_path, "https://example.org/p", "not on the page", lambda u: (u, PAGE))
    reloaded = AcceptedLog(log.path).facts()
    assert out["conclusion"] == "CONTRADICTED"
    assert len(reloaded) == 1
    assert reloaded[0].statement == log.facts()[0].statement
    assert reloaded[0].statement.startswith("CONTRADICTED:")
    assert reloaded[0].sources == log.facts()[0].sources


def test_replacement_character_does_not_match_invalid_utf8(tmp_path):
    # Invalid UTF-8 is refused before a conclusion is stored. A replacement
    # character is therefore not CONTRADICTED from a decoded stand-in.
    body = b"\xff\xfe hello"
    out, log = run_claim(tmp_path, "https://example.org/p", "\ufffd", lambda u: (u, body))
    assert out == {"conclusion": "BLOCKED", "reason": "body is not valid UTF-8"}
    assert log.facts() == []


def test_multibyte_quote_is_anchored_to_raw_utf8_bytes(tmp_path):
    poisoned = "café".encode("utf-8") + b" \xff"
    blocked, blocked_log = run_claim(
        tmp_path, "https://example.org/p", "café", lambda u: (u, poisoned),
    )
    assert blocked == {"conclusion": "BLOCKED", "reason": "body is not valid UTF-8"}
    assert blocked_log.facts() == []

    (tmp_path / "valid").mkdir()
    body = "pré café".encode("utf-8")
    quote = "café"
    needle = quote.encode("utf-8")
    out, _ = run_claim(tmp_path / "valid", "https://example.org/p", quote, lambda u: (u, body))
    assert out["conclusion"] == "SUPPORTED"
    assert out["anchor"]["offset"] == body.find(needle)
    assert out["anchor"]["length"] == len(needle)
    assert body[out["anchor"]["offset"]:out["anchor"]["offset"] + out["anchor"]["length"]] == needle


def test_quote_after_multibyte_character_uses_byte_offset(tmp_path):
    body = "äX".encode("utf-8")
    out, _ = run_claim(tmp_path, "https://example.org/p", "X", lambda u: (u, body))
    assert out["conclusion"] == "SUPPORTED"
    assert out["anchor"]["offset"] == 2
    assert out["anchor"]["length"] == 1


def test_latin1_bytes_do_not_support_utf8_quote(tmp_path):
    body = "café".encode("latin-1")
    out, log = run_claim(tmp_path, "https://example.org/p", "café", lambda u: (u, body))
    assert out == {"conclusion": "BLOCKED", "reason": "body is not valid UTF-8"}
    assert log.facts() == []


def test_real_replacement_character_in_bytes_is_supported(tmp_path):
    needle = "\ufffd".encode("utf-8")
    body = b"see " + needle + b" here"
    out, _ = run_claim(tmp_path, "https://example.org/p", "\ufffd", lambda u: (u, body))
    assert out["conclusion"] == "SUPPORTED"
    assert out["anchor"]["offset"] == body.find(needle)
    assert out["anchor"]["length"] == len(needle)


def test_multibyte_prefix_anchor_is_byte_offset_into_original_body(tmp_path):
    body = "€ 10 genau".encode("utf-8")
    quote = "10 genau"
    encoded = quote.encode("utf-8")
    out, log = run_claim(tmp_path, "https://example.org/p", quote, lambda u: (u, body))
    offset = out["anchor"]["offset"]
    length = out["anchor"]["length"]
    assert out["conclusion"] == "SUPPORTED"
    assert offset == body.find(encoded)
    assert length == len(encoded)
    assert body[offset:offset + length] == encoded
    assert log.facts()[0].statement.startswith("SUPPORTED:")


def test_replacement_character_quote_is_not_supported(tmp_path):
    quote = "hello \ufffd world"
    blocked, blocked_log = run_claim(
        tmp_path, "https://example.org/p", quote, lambda u: (u, b"hello \xff world"),
    )
    assert blocked == {"conclusion": "BLOCKED", "reason": "body is not valid UTF-8"}
    assert blocked_log.facts() == []

    (tmp_path / "valid").mkdir()
    body = b"hello world"
    out, log = run_claim(tmp_path / "valid", "https://example.org/p", quote, lambda u: (u, body))
    assert out["conclusion"] == "CONTRADICTED"
    assert out["anchor"]["offset"] is None
    assert log.facts()[0].statement.startswith("CONTRADICTED:")
    assert quote.encode("utf-8") not in body
