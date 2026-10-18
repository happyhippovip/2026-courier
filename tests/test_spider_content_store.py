"""Provenance-store integrity for the spider minimum slice (no network).

Pins branches of courier_runtime/spider_slice.py that the happy-path
slice test does not cover:
- ContentStore.get rejects a tampered blob instead of serving it.
- A CONTRADICTED verdict still records ledger provenance with null offset.
- Non-UTF8 fetch bytes never crash the quote check (fail-closed BLOCKED, nothing stored).
"""
import pytest

from courier_runtime.continuation import AcceptedLog
from courier_runtime.spider_slice import ContentStore, ResearchRequest, check_claim


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def make_request(url="https://example.org/p", quote="hello", origin="https://example.org"):
    return ResearchRequest("wk-spider-store", url, quote, origin)


def run_claim(tmp_path, request, body):
    log = AcceptedLog(str(tmp_path / "store.jsonl"))
    out = check_claim(request, lambda u: (u, body), ContentStore(), log, Clock())
    return out, log


def test_tampered_blob_is_rejected_on_get():
    store = ContentStore()
    digest = store.put(b"genuine bytes")
    store._blobs[digest] = b"forged bytes"
    with pytest.raises(ValueError, match="tamper"):
        store.get(digest)


def test_contradicted_verdict_has_null_offset_but_keeps_provenance(tmp_path):
    out, log = run_claim(tmp_path, make_request(quote="absent phrase"), b"<p>hello world</p>")
    assert out["conclusion"] == "CONTRADICTED"
    assert out["anchor"]["offset"] is None
    assert out["anchor"]["length"] == len("absent phrase")
    assert log.facts()[0].sources[0] == "content:" + out["anchor"]["sha256"]


def test_non_utf8_body_is_blocked_without_crash(tmp_path):
    out, log = run_claim(tmp_path, make_request(), b"\xff\xfe\x00hello world")
    assert out["conclusion"] == "BLOCKED"
    assert "UTF-8" in out["reason"]
    assert "anchor" not in out
    assert log.facts() == []


def test_unexpected_fetcher_shape_is_blocked_without_fact(tmp_path):
    log = AcceptedLog(str(tmp_path / "store.jsonl"))
    out = check_claim(make_request(), lambda u: None, ContentStore(), log, Clock())
    assert out["conclusion"] == "BLOCKED"
    assert "unexpected result" in out["reason"]
    assert log.facts() == []


def test_disallowed_charset_is_blocked_without_fact(tmp_path):
    log = AcceptedLog(str(tmp_path / "store.jsonl"))
    fetch = lambda u: (u, b"<p>hello</p>", "text/html; charset=latin1")
    out = check_claim(make_request(), fetch, ContentStore(), log, Clock())
    assert out["conclusion"] == "BLOCKED"
    assert "contract" in out["reason"]
    assert log.facts() == []
