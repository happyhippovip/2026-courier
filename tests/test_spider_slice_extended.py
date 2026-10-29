import pytest
import hashlib
from courier_runtime.continuation import AcceptedLog
from courier_runtime.spider_slice import ContentStore, ResearchRequest, check_claim


class Clock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def test_content_store_put_and_get():
    store = ContentStore()
    data = b"Deterministic payload 2026"
    digest = store.put(data)
    assert digest == hashlib.sha256(data).hexdigest()
    assert store.get(digest) == data


def test_content_store_tamper_detection():
    store = ContentStore()
    data = b"Original bytes"
    digest = store.put(data)
    # Force tamper
    store._blobs[digest] = b"Tampered bytes"
    with pytest.raises(ValueError, match="store tamper detected"):
        store.get(digest)


def test_check_claim_non_https_scheme_blocked(tmp_path):
    log = AcceptedLog(str(tmp_path / "log.jsonl"))
    req = ResearchRequest(
        workkey="wk-test",
        url="ftp://example.com/file.txt",
        quote="data",
        approved_origin="ftp://example.com"
    )
    res = check_claim(req, lambda u: (u, b"data"), ContentStore(), log, Clock())
    assert res["conclusion"] == "BLOCKED"
    assert "not the approved origin" in res["reason"]
    assert len(log.facts()) == 0


def test_check_claim_port_mismatch_blocked(tmp_path):
    log = AcceptedLog(str(tmp_path / "log.jsonl"))
    req = ResearchRequest(
        workkey="wk-test",
        url="https://example.com:8443/file.txt",
        quote="data",
        approved_origin="https://example.com"
    )
    res = check_claim(req, lambda u: (u, b"data"), ContentStore(), log, Clock())
    assert res["conclusion"] == "BLOCKED"
    assert len(log.facts()) == 0


def test_check_claim_redirect_port_shift_blocked(tmp_path):
    log = AcceptedLog(str(tmp_path / "log.jsonl"))
    req = ResearchRequest(
        workkey="wk-test",
        url="https://example.com/start",
        quote="data",
        approved_origin="https://example.com"
    )
    fetch = lambda u: ("https://example.com:8080/landing", b"data")
    res = check_claim(req, fetch, ContentStore(), log, Clock())
    assert res["conclusion"] == "BLOCKED"
    assert res["reason"] == "redirect left the approved origin"
    assert len(log.facts()) == 0


def test_check_claim_quote_boundary_matches(tmp_path):
    log = AcceptedLog(str(tmp_path / "log.jsonl"))
    body = "Leading padding text — EXACT_QUOTE_TARGET — trailing text".encode("utf-8")
    req = ResearchRequest(
        workkey="wk-boundary",
        url="https://example.org/doc",
        quote="EXACT_QUOTE_TARGET",
        approved_origin="https://example.org"
    )
    clock = Clock(500.0)
    res = check_claim(req, lambda u: (u, body), ContentStore(), log, clock)
    assert res["conclusion"] == "SUPPORTED"
    assert res["anchor"]["offset"] == body.decode("utf-8").find("EXACT_QUOTE_TARGET")
    assert res["anchor"]["length"] == len("EXACT_QUOTE_TARGET")
    assert res["anchor"]["url"] == "https://example.org/doc"
    assert len(log.facts()) == 1
    fact = log.facts()[0]
    assert fact.workkey == "wk-boundary"
    assert fact.accepted_at == 500.0


def test_check_claim_partial_unicode_replace_safety(tmp_path):
    log = AcceptedLog(str(tmp_path / "log.jsonl"))
    # Corrupt byte sequence
    corrupt_body = b"Valid prefix \xff\xfe and valid suffix"
    req = ResearchRequest(
        workkey="wk-unicode",
        url="https://example.org/doc",
        quote="valid suffix",
        approved_origin="https://example.org"
    )
    res = check_claim(req, lambda u: (u, corrupt_body), ContentStore(), log, Clock())
    assert res["conclusion"] == "SUPPORTED"
    assert res["anchor"]["length"] == len("valid suffix")
    assert len(log.facts()) == 1


def test_check_claim_contradicted_leaves_none_offset(tmp_path):
    log = AcceptedLog(str(tmp_path / "log.jsonl"))
    body = b"Document discussing apples and oranges"
    req = ResearchRequest(
        workkey="wk-contra",
        url="https://example.org/report",
        quote="bananas",
        approved_origin="https://example.org"
    )
    res = check_claim(req, lambda u: (u, body), ContentStore(), log, Clock())
    assert res["conclusion"] == "CONTRADICTED"
    assert res["anchor"]["offset"] is None
    assert res["anchor"]["length"] == len("bananas")
    assert len(log.facts()) == 1
    assert "CONTRADICTED: 'bananas'" in log.facts()[0].statement
