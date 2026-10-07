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
