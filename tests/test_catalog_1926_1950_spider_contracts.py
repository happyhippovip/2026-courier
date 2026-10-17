"""Catalog 1926-1950 contracts for the spider slice.

Encoding is fail-closed UTF-8. A declared Content-Type is bounded to text
documents. A fetched body over the prepared cap is refused before it is
stored. Nothing here opens a socket or spends money.
"""
from pathlib import Path

import pytest

from courier_runtime.continuation import AcceptedLog
from courier_runtime.spider_slice import (
    MAX_FETCH_BYTES,
    ContentStore,
    FetchTooLarge,
    ResearchRequest,
    check_claim,
    parse_content_type,
    take_bounded,
)


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


ORIGIN = "https://example.org"
URL = ORIGIN + "/p"
PAGE = b"<p>Courier keeps a conclusion supported over time.</p>"


class CountingStore(ContentStore):
    def __init__(self):
        super().__init__()
        self.puts = 0

    def put(self, data):
        self.puts += 1
        return super().put(data)


def claim(tmp_path, body, quote, content_type=None, max_bytes=MAX_FETCH_BYTES):
    def fetch(url):
        if content_type is None:
            return (url, body)
        return (url, body, content_type)

    return claim_fetch(tmp_path, fetch, quote=quote, max_bytes=max_bytes)


def claim_fetch(tmp_path, fetch, quote="x", max_bytes=MAX_FETCH_BYTES):
    store = CountingStore()
    path = tmp_path / "a.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    log = AcceptedLog(str(path))
    out = check_claim(
        ResearchRequest("wk-s", URL, quote, ORIGIN),
        fetch,
        store,
        log,
        Clock(),
        max_bytes=max_bytes,
    )
    return out, log, store


# -- 1926 encoding negative path -------------------------------------------------


def test_invalid_utf8_does_not_support_replacement_quote(tmp_path):
    out, log, store = claim(tmp_path, b"\xff", "\ufffd")
    assert out == {"conclusion": "BLOCKED", "reason": "body is not valid UTF-8"}
    assert log.facts() == []
    assert store.puts == 0


def test_truncated_multibyte_is_blocked(tmp_path):
    out, log, store = claim(tmp_path, b"caf\xc3", "caf")
    assert out["conclusion"] == "BLOCKED"
    assert log.facts() == []
    assert store.puts == 0


def test_valid_utf8_quote_still_supported(tmp_path):
    body = "Größe".encode()
    out, log, store = claim(tmp_path, body, "Größe")
    assert out["conclusion"] == "SUPPORTED"
    assert out["anchor"]["offset"] == 0
    assert store.puts == 1
    assert log.facts()[0].sources[0] == "content:" + out["anchor"]["sha256"]


# -- 1927 encoding reload --------------------------------------------------------


def test_valid_decision_reloads_and_repeats(tmp_path):
    out, log, _store = claim(tmp_path, PAGE, "conclusion supported")
    reloaded = AcceptedLog(str(tmp_path / "a.jsonl"))
    assert reloaded.facts()[0].statement == log.facts()[0].statement
    assert reloaded.facts()[0].sources == log.facts()[0].sources
    again, again_log, _store = claim(tmp_path / "second", PAGE, "conclusion supported")
    assert again["conclusion"] == out["conclusion"] == "SUPPORTED"
    assert again["anchor"]["sha256"] == out["anchor"]["sha256"]
    assert len(again_log.facts()) == 1


def test_invalid_utf8_stays_blocked_on_second_run(tmp_path):
    first, first_log, first_store = claim(tmp_path, b"\xff", "\ufffd")
    second, second_log, second_store = claim(tmp_path / "second", b"\xff", "\ufffd")
    assert first == second
    assert first["conclusion"] == "BLOCKED"
    assert first_log.facts() == [] and second_log.facts() == []
    assert first_store.puts == 0 and second_store.puts == 0


def test_repeat_on_same_log_appends_a_second_fact(tmp_path):
    """AcceptedLog stays append-only. A second run is reproducible, not deduped."""
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    store = ContentStore()
    request = ResearchRequest("wk-s", URL, "conclusion supported", ORIGIN)
    fetch = lambda _url: (_url, PAGE)
    one = check_claim(request, fetch, store, log, Clock())
    two = check_claim(request, fetch, ContentStore(), log, Clock())
    assert one["anchor"]["sha256"] == two["anchor"]["sha256"]
    assert len(log.facts()) == 2


# -- 1934-1937 content type ------------------------------------------------------


@pytest.mark.parametrize("header", [
    "text/html; charset=utf-8",
    'text/html; charset="UTF-8"',
    "text/plain",
    "application/xhtml+xml; charset=us-ascii",
])
def test_declared_text_types_can_support_a_quote(tmp_path, header):
    out, log, store = claim(tmp_path, b"hello", "hello", content_type=header)
    assert out["conclusion"] == "SUPPORTED"
    assert store.puts == 1
    assert len(log.facts()) == 1


@pytest.mark.parametrize("header,reason_part", [
    ("application/octet-stream", "application/octet-stream"),
    ("image/png", "image/png"),
    ("text/html; charset=iso-8859-1", "iso-8859-1"),
    ("text/html; charset=utf-16", "utf-16"),
    ("text/html;", "outside the contract"),
    ("text/html; charset=utf-8; charset=utf-8", "outside the contract"),
    ("", "outside the contract"),
])
def test_declared_type_outside_contract_is_blocked(tmp_path, header, reason_part):
    out, log, store = claim_fetch(
        tmp_path,
        lambda url: (url, b"hello", header),
        quote="hello",
    )
    assert out["conclusion"] == "BLOCKED"
    assert reason_part in out["reason"]
    assert log.facts() == []
    assert store.puts == 0


def test_missing_content_type_stays_on_the_utf8_path(tmp_path):
    out, _log, store = claim(tmp_path, b"hello", "hello")
    assert out["conclusion"] == "SUPPORTED"
    assert store.puts == 1


def test_list_pair_from_the_fetcher_still_supports(tmp_path):
    out, _log, store = claim_fetch(tmp_path, lambda url: [url, b"hello"], quote="hello")
    assert out["conclusion"] == "SUPPORTED"
    assert store.puts == 1


def test_us_ascii_rejects_high_bytes(tmp_path):
    out, log, store = claim(
        tmp_path, "ä".encode(), "ä", content_type="text/plain; charset=us-ascii",
    )
    assert out == {"conclusion": "BLOCKED", "reason": "body is not US-ASCII"}
    assert log.facts() == []
    assert store.puts == 0


def test_content_type_block_survives_a_second_run(tmp_path):
    fetch = lambda url: (url, b"hello", "application/octet-stream")
    first, first_log, first_store = claim_fetch(tmp_path, fetch, quote="hello")
    second, second_log, second_store = claim_fetch(tmp_path / "second", fetch, quote="hello")
    assert first == second
    assert first_log.facts() == [] and second_log.facts() == []
    assert first_store.puts == 0 and second_store.puts == 0


def test_parse_content_type_bounds():
    assert parse_content_type("Text/HTML; Charset=UTF-8") == ("text/html", "utf-8")
    with pytest.raises(ValueError):
        parse_content_type("text/html; charset=" + ("a" * 300))
    with pytest.raises(ValueError):
        parse_content_type(None)


# -- 1944-1947 fetch size --------------------------------------------------------


def test_take_bounded_keeps_an_exact_fit_and_drops_the_overflow():
    assert take_bounded([b"ab", b"cd"], 4) == b"abcd"
    assert take_bounded([b""], 0) == b""
    with pytest.raises(FetchTooLarge) as caught:
        take_bounded([b"abcd", b"ef"], 5)
    assert caught.value.max_bytes == 5
    with pytest.raises(FetchTooLarge):
        take_bounded([b"a"], 0)
    with pytest.raises(TypeError):
        take_bounded(["ab"], 4)
    with pytest.raises(ValueError):
        take_bounded([b"a"], True)


def test_body_over_the_cap_is_blocked_and_not_stored(tmp_path):
    out, log, store = claim(tmp_path, b"hello!", "hello", max_bytes=5)
    assert out == {"conclusion": "BLOCKED", "reason": "fetch body exceeds 5 bytes"}
    assert log.facts() == []
    assert store.puts == 0


def test_body_exactly_at_the_cap_is_stored(tmp_path):
    out, log, store = claim(tmp_path, b"hello", "hello", max_bytes=5)
    assert out["conclusion"] == "SUPPORTED"
    assert store.puts == 1
    assert len(log.facts()) == 1


def test_default_cap_blocks_one_byte_over_without_a_custom_limit(tmp_path):
    body = b"x" * (MAX_FETCH_BYTES + 1)
    out, log, store = claim(tmp_path, body, "x")
    assert out["conclusion"] == "BLOCKED"
    assert str(MAX_FETCH_BYTES) in out["reason"]
    assert log.facts() == []
    assert store.puts == 0
    assert MAX_FETCH_BYTES == 1_048_576


def test_non_bytes_body_is_blocked(tmp_path):
    out, log, store = claim_fetch(tmp_path, lambda url: (url, "hello"), quote="hello")
    assert out == {"conclusion": "BLOCKED", "reason": "fetch body is not bytes"}
    assert log.facts() == []
    assert store.puts == 0


def test_oversize_stays_blocked_on_second_run(tmp_path):
    fetch = lambda url: (url, b"abcdef")
    first, first_log, first_store = claim_fetch(tmp_path, fetch, quote="abc", max_bytes=3)
    second, second_log, second_store = claim_fetch(
        tmp_path / "second", fetch, quote="abc", max_bytes=3,
    )
    assert first == second
    assert "exceeds 3 bytes" in first["reason"]
    assert first_log.facts() == [] and second_log.facts() == []
    assert first_store.puts == 0 and second_store.puts == 0


def test_windows_worker_snapshot_matches_live_module():
    root = Path(__file__).resolve().parents[1]
    live = (root / "courier_runtime" / "spider_slice.py").read_bytes()
    snap = (root / "scripts" / "windows_worker" / "dist" / "libs" / "courier_runtime" / "spider_slice.py").read_bytes()
    assert live == snap


def test_size_is_checked_before_a_bad_content_type(tmp_path):
    fetch = lambda url: (url, b"abcdef", "application/octet-stream")
    out, _log, store = claim_fetch(tmp_path, fetch, quote="a", max_bytes=3)
    assert out["reason"] == "fetch body exceeds 3 bytes"
    assert store.puts == 0
