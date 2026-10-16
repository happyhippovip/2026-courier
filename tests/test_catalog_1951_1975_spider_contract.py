"""Catalog 1951-1975 pins for the existing spider claim check.

check_claim is deterministic and has no socket of its own. An unapproved
origin is not fetched and is not recorded. A supported quote is an accepted
fact that reloads unchanged. Nothing here opens a network connection or adds
a proposal store.
"""
import socket

from courier_runtime.continuation import AcceptedLog
from courier_runtime.spider_slice import ContentStore, ResearchRequest, check_claim
from courier_runtime.update_gate import CapabilityState, compare


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


PAGE = b"<p>Courier keeps a conclusion supported over time.</p>"
APPROVED = "https://example.org"


def run(tmp_path, url, quote, fetch, origin=APPROVED, name="a.jsonl"):
    log = AcceptedLog(str(tmp_path / name))
    out = check_claim(
        ResearchRequest("wk-catalog", url, quote, origin),
        fetch,
        ContentStore(),
        log,
        Clock(),
    )
    return out, log


def test_foreign_https_origin_does_not_fetch_or_record(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return url, PAGE

    out, log = run(tmp_path, "https://evil.example/p", "x", fetch)
    assert calls == []
    assert out["conclusion"] == "BLOCKED"
    assert "anchor" not in out
    assert log.facts() == []


def test_cleartext_http_does_not_fetch_or_record(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return url, PAGE

    out, log = run(tmp_path, "http://example.org/p", "x", fetch)
    assert calls == []
    assert out["conclusion"] == "BLOCKED"
    assert log.facts() == []


def test_approved_origin_fetches_once_and_can_support(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return url, PAGE

    out, log = run(tmp_path, "https://example.org/p", "conclusion supported", fetch)
    assert calls == ["https://example.org/p"]
    assert out["conclusion"] == "SUPPORTED"
    assert out["anchor"]["url"] == "https://example.org/p"
    assert log.facts()[0].sources[0] == "content:" + out["anchor"]["sha256"]


def test_redirect_off_origin_is_fetched_once_then_blocked_without_a_fact(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return "https://evil.example/landing", PAGE

    out, log = run(tmp_path, "https://example.org/p", "conclusion supported", fetch)
    assert calls == ["https://example.org/p"]
    assert out["conclusion"] == "BLOCKED"
    assert "anchor" not in out
    assert log.facts() == []


def test_check_claim_itself_does_not_open_a_socket(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("extractor opened a socket")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    calls = []

    def fetch(url):
        calls.append(url)
        return url, PAGE

    out, log = run(tmp_path, "https://evil.example/p", "x", fetch)
    assert calls == []
    assert out["conclusion"] == "BLOCKED"
    assert log.facts() == []


def test_untrusted_link_is_not_recorded_as_an_accepted_fact(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return url, PAGE

    out, log = run(tmp_path, "https://evil.example/secret", "conclusion supported", fetch)
    assert out["conclusion"] == "BLOCKED"
    assert calls == []
    assert log.facts() == []
    reopened = AcceptedLog(log.path)
    assert reopened.facts() == []


def test_supported_fact_reloads_and_a_later_block_does_not_append(tmp_path):
    def fetch(url):
        return url, PAGE

    out, log = run(tmp_path, "https://example.org/p", "conclusion supported", fetch)
    digest = out["anchor"]["sha256"]
    reopened = AcceptedLog(log.path)
    facts = reopened.facts("wk-catalog")
    assert len(facts) == 1
    assert facts[0].statement.startswith("SUPPORTED:")
    assert f"content:{digest}" in facts[0].sources

    def refuse(_url):
        raise AssertionError("fetch must not run")

    blocked, same = run(
        tmp_path,
        "https://evil.example/p",
        "conclusion supported",
        refuse,
        name="a.jsonl",
    )
    assert blocked["conclusion"] == "BLOCKED"
    assert len(same.facts()) == 1
    assert f"content:{digest}" in AcceptedLog(log.path).facts()[0].sources


def test_repeated_block_stays_idempotent(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return url, PAGE

    first, log = run(tmp_path, "https://evil.example/p", "x", fetch)
    second, _ = run(tmp_path, "https://evil.example/p", "x", fetch, name="a.jsonl")
    assert first == second
    assert first["conclusion"] == "BLOCKED"
    assert calls == []
    assert log.facts() == []


def test_proposed_capabilities_are_not_previously_verified():
    before = CapabilityState("1.0.0", {"LEDGER-01": True, "GOLDEN-01": True, "HUB-03": False}, "d1")
    after = CapabilityState("1.1.0", {"LEDGER-01": True, "GOLDEN-01": True, "HUB-03": True}, "d1")
    result = compare(before, after)
    previously_verified = {name for name, ok in before.capabilities.items() if ok}
    assert result["decision"] == "ACCEPT"
    assert result["proposed"] == ["HUB-03"]
    assert set(result["proposed"]).isdisjoint(previously_verified)
    assert "HUB-03" not in previously_verified
