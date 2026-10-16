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


def test_redirect_hop_chain_within_approved_origin_supported(tmp_path):
    hops = [
        "https://example.org/step1",
        "https://example.org/step2",
        "https://example.org/final",
    ]
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    req = ResearchRequest("wk-hop", "https://example.org/step1", "conclusion supported", "https://example.org", max_hops=4)
    out = check_claim(req, lambda u: ("https://example.org/final", PAGE, hops), ContentStore(), log, Clock())
    assert out["conclusion"] == "SUPPORTED"
    assert out["anchor"]["hops"] == hops
    assert len(log.facts()) == 1


def test_redirect_loop_detected_and_blocked(tmp_path):
    hops = [
        "https://example.org/a",
        "https://example.org/b",
        "https://example.org/a",
    ]
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    req = ResearchRequest("wk-loop", "https://example.org/a", "conclusion supported", "https://example.org")
    out = check_claim(req, lambda u: ("https://example.org/a", PAGE, hops), ContentStore(), log, Clock())
    assert out["conclusion"] == "BLOCKED"
    assert "loop detected" in out["reason"]
    assert log.facts() == []


def test_redirect_hop_limit_exceeded_blocked(tmp_path):
    hops = [f"https://example.org/hop{i}" for i in range(6)]
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    req = ResearchRequest("wk-limit", "https://example.org/hop0", "x", "https://example.org", max_hops=3)
    out = check_claim(req, lambda u: (hops[-1], PAGE, hops), ContentStore(), log, Clock())
    assert out["conclusion"] == "BLOCKED"
    assert "hop limit exceeded" in out["reason"]
    assert log.facts() == []


def test_intermediate_hop_outside_grant_blocked(tmp_path):
    hops = [
        "https://example.org/entry",
        "https://tracker.thirdparty.com/redirect",
        "https://example.org/final",
    ]
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    req = ResearchRequest("wk-leak", "https://example.org/entry", "x", "https://example.org")
    out = check_claim(req, lambda u: ("https://example.org/final", PAGE, hops), ContentStore(), log, Clock())
    assert out["conclusion"] == "BLOCKED"
    assert "left the approved origin" in out["reason"]
    assert log.facts() == []


def test_url_port_difference_respected(tmp_path):
    # Port 443 normalized as default https
    out, log = run_claim(tmp_path, "https://example.org:443/p", "conclusion supported", lambda u: (u, PAGE))
    assert out["conclusion"] == "SUPPORTED"

    # Non-standard port 8443 rejected when grant is standard https://example.org
    (tmp_path / "port").mkdir()
    log2 = AcceptedLog(str(tmp_path / "port" / "a.jsonl"))
    req = ResearchRequest("wk-port", "https://example.org:8443/p", "x", "https://example.org")
    out2 = check_claim(req, lambda u: (u, PAGE), ContentStore(), log2, Clock())
    assert out2["conclusion"] == "BLOCKED"
    assert "not the approved origin" in out2["reason"]


def test_hostname_normalization_case_and_dot(tmp_path):
    out, log = run_claim(tmp_path, "https://EXAMPLE.ORG./p", "conclusion supported", lambda u: (u, PAGE))
    assert out["conclusion"] == "SUPPORTED"
    assert out["anchor"]["canonical_url"] == "https://example.org/p"


def test_canonical_url_and_effect_key_determinism(tmp_path):
    log1 = AcceptedLog(str(tmp_path / "a1.jsonl"))
    log2 = AcceptedLog(str(tmp_path / "a2.jsonl"))
    store = ContentStore()

    # Two URLs with redundant slashes and unordered query params
    u1 = "https://example.org//a///b?b=2&a=1#frag"
    u2 = "https://EXAMPLE.ORG/a/b?a=1&b=2"
    req1 = ResearchRequest("wk1", u1, "conclusion supported", "https://example.org")
    req2 = ResearchRequest("wk2", u2, "conclusion supported", "https://example.org")

    out1 = check_claim(req1, lambda u: (u, PAGE), store, log1, Clock())
    out2 = check_claim(req2, lambda u: (u, PAGE), store, log2, Clock())

    assert out1["conclusion"] == "SUPPORTED" and out2["conclusion"] == "SUPPORTED"
    assert out1["anchor"]["canonical_url"] == "https://example.org/a/b?a=1&b=2"
    assert out2["anchor"]["canonical_url"] == "https://example.org/a/b?a=1&b=2"
    assert out1["anchor"]["effect_key"] == out2["anchor"]["effect_key"]


def test_policy_epoch_invalidation(tmp_path):
    log1 = AcceptedLog(str(tmp_path / "ep1.jsonl"))
    log2 = AcceptedLog(str(tmp_path / "ep2.jsonl"))
    req_ep1 = ResearchRequest("wk-ep1", "https://example.org/p", "conclusion supported", "https://example.org", policy_epoch=1)
    req_ep2 = ResearchRequest("wk-ep2", "https://example.org/p", "conclusion supported", "https://example.org", policy_epoch=2)

    out1 = check_claim(req_ep1, lambda u: (u, PAGE), ContentStore(), log1, Clock())
    out2 = check_claim(req_ep2, lambda u: (u, PAGE), ContentStore(), log2, Clock())

    assert out1["anchor"]["effect_key"] != out2["anchor"]["effect_key"]
    assert out1["anchor"]["policy_epoch"] == 1
    assert out2["anchor"]["policy_epoch"] == 2


def test_empty_or_whitespace_quote_rejected(tmp_path):
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    for empty in ("", "   ", "\t\n"):
        req = ResearchRequest("wk-empty", "https://example.org/p", empty, "https://example.org")
        out = check_claim(req, lambda u: (u, PAGE), ContentStore(), log, Clock())
        assert out["conclusion"] == "REJECTED"
        assert "empty quote" in out["reason"]
    assert log.facts() == []


def test_payload_size_limit_exceeded_blocked(tmp_path):
    big_page = b"A" * 1000
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    req = ResearchRequest("wk-big", "https://example.org/p", "A", "https://example.org", max_bytes=500)
    out = check_claim(req, lambda u: (u, big_page), ContentStore(), log, Clock())
    assert out["conclusion"] == "BLOCKED"
    assert "payload exceeded size limit" in out["reason"]
    assert log.facts() == []


def test_offline_untrusted_link_extraction():
    from courier_runtime.spider_slice import extract_untrusted_links
    html = """
    <html><body>
        <a href="/relative/path">Relative</a>
        <a href="https://example.org/absolute?b=2&a=1">Absolute</a>
        <a href="#fragment">Fragment</a>
        <a href="javascript:alert(1)">JS</a>
        <a href="mailto:test@example.org">Mail</a>
    </body></html>
    """
    links = extract_untrusted_links(html, "https://example.org/root/")
    assert len(links) == 2
    assert all(item["status"] == "PROPOSED" for item in links)
    assert links[0]["url"] == "https://example.org/relative/path"
    assert links[1]["url"] == "https://example.org/absolute?a=1&b=2"


def test_doi_syntax_offline_validation():
    from courier_runtime.spider_slice import verify_doi_syntax
    valid_cases = [
        "10.1000/182",
        "10.1038/nature.2014.16434",
        "doi:10.1109/5.771073",
        "https://doi.org/10.1002/(SICI)1097-0142(19970815)80:4<654::AID-CNCR4>3.0.CO;2-9",
    ]
    invalid_cases = [
        "",
        "not-a-doi",
        "11.1000/182",
        "10.999",
        "10./empty-registrant",
    ]
    for doi in valid_cases:
        assert verify_doi_syntax(doi) is True, f"Expected {doi} to be valid"
    for doi in invalid_cases:
        assert verify_doi_syntax(doi) is False, f"Expected {doi} to be invalid"


def test_isbn_checksum_offline_validation():
    from courier_runtime.spider_slice import verify_isbn_checksum
    # Valid ISBN-10 and ISBN-13
    valid = [
        "0-306-40615-2",
        "0306406152",
        "0-8044-2957-X",
        "978-0-306-40615-7",
        "9780306406157",
    ]
    invalid = [
        "0-306-40615-3",
        "0-8044-2957-9",
        "978-0-306-40615-8",
        "short",
        "not-an-isbn",
        "123456789012345",
    ]
    for isbn in valid:
        assert verify_isbn_checksum(isbn) is True, f"Expected {isbn} to be valid"
    for isbn in invalid:
        assert verify_isbn_checksum(isbn) is False, f"Expected {isbn} to be invalid"
