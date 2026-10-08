import pytest
import hashlib
from courier_runtime.continuation import AcceptedLog
from courier_runtime.spider_slice import ContentStore, ResearchRequest, check_claim


class Clock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t


def test_content_store_tamper_detection():
    store = ContentStore()
    data = b"trusted deterministic payload"
    digest = store.put(data)
    assert digest == hashlib.sha256(data).hexdigest()
    assert store.get(digest) == data

    # Tamper with internal dictionary
    store._blobs[digest] = b"tampered corrupt payload"
    with pytest.raises(ValueError) as exc:
        store.get(digest)
    assert "store tamper detected" in str(exc.value)


def test_check_claim_non_https_blocked(tmp_path):
    log = AcceptedLog(str(tmp_path / "facts.jsonl"))
    store = ContentStore()
    clock = Clock()

    req = ResearchRequest(
        workkey="wk-http",
        url="http://insecure.example.org/doc",
        quote="secure information",
        approved_origin="http://insecure.example.org"
    )
    res = check_claim(req, lambda u: (u, b"secure information"), store, log, clock)
    assert res["conclusion"] == "BLOCKED"
    assert "is not the approved origin" in res["reason"]
    assert log.facts() == []


def test_check_claim_encoding_and_offsets(tmp_path):
    log = AcceptedLog(str(tmp_path / "facts.jsonl"))
    store = ContentStore()
    clock = Clock(500.0)

    # Unicode with multibyte characters
    body = "Courier Symphony: Begründung und Fristen § 41 VwVfG.".encode("utf-8")
    quote = "§ 41 VwVfG"
    req = ResearchRequest(
        workkey="wk-unicode",
        url="https://bund.de/gesetz",
        quote=quote,
        approved_origin="https://bund.de"
    )
    res = check_claim(req, lambda u: (u, body), store, log, clock)
    assert res["conclusion"] == "SUPPORTED"
    assert res["anchor"]["length"] == len(quote)
    assert res["anchor"]["url"] == "https://bund.de/gesetz"
    assert res["anchor"]["offset"] is not None

    facts = log.facts("wk-unicode")
    assert len(facts) == 1
    assert facts[0].accepted_at == 500.0
    assert "SUPPORTED" in facts[0].statement
    assert quote in facts[0].statement
