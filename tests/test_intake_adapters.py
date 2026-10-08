import hashlib
import json
import pytest
from unittest.mock import MagicMock, patch

from courier_adapters.decrypt_intake import fetch_decrypt
from courier_adapters.cryptoknowmics_intake import HTMLStripper, remove_tags, fetch_cryptoknowmics


RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
    <title>Decrypt</title>
    <item>
        <title>Crypto Regulation Update</title>
        <link>https://decrypt.co/12345/crypto-reg</link>
        <pubDate>Thu, 08 Oct 2026 12:00:00 GMT</pubDate>
        <dc:creator>Jane Doe</dc:creator>
        <content:encoded><![CDATA[<p>Full breakdown of regulatory movements in crypto.</p>]]></content:encoded>
    </item>
    <item>
        <title>Bitcoin Mining Trends</title>
        <link>https://decrypt.co/67890/btc-mining</link>
        <pubDate>Thu, 08 Oct 2026 13:00:00 GMT</pubDate>
        <description>Short summary of mining difficulty adjustments.</description>
    </item>
</channel>
</rss>
"""


def test_decrypt_intake_creates_tasks_and_handles_duplicates():
    recorded_posts = []

    def mock_get(url, **kwargs):
        res = MagicMock()
        res.raise_for_status.return_value = None
        res.content = RSS_SAMPLE
        return res

    def mock_post(url, **kwargs):
        recorded_posts.append((url, kwargs))
        res = MagicMock()
        # First call 201 created, second call 200 duplicate
        if len(recorded_posts) == 1:
            res.status_code = 201
        else:
            res.status_code = 200
        return res

    with patch("requests.get", side_effect=mock_get), patch("requests.post", side_effect=mock_post):
        fetch_decrypt("http://127.0.0.1:8080", "hub-token-123")

    assert len(recorded_posts) == 2

    # Check task 1
    url1, kwargs1 = recorded_posts[0]
    payload1 = kwargs1["json"]
    assert payload1["adapter"] == "local_json_delivery"
    assert payload1["effect_class"] == "idempotent"
    assert payload1["params"]["title"] == "Crypto Regulation Update"
    assert payload1["params"]["author"] == "Jane Doe"
    assert payload1["params"]["content_text"] == "<p>Full breakdown of regulatory movements in crypto.</p>"
    expected_id1 = hashlib.sha256("https://decrypt.co/12345/crypto-reg".encode("utf-8")).hexdigest()
    assert payload1["idempotency_key"] == f"decrypt:{expected_id1}"

    # Check task 2 (no dc:creator, uses description as content_text)
    url2, kwargs2 = recorded_posts[1]
    payload2 = kwargs2["json"]
    assert payload2["params"]["title"] == "Bitcoin Mining Trends"
    assert payload2["params"]["author"] == "Unknown"
    assert payload2["params"]["content_text"] == "Short summary of mining difficulty adjustments."


def test_cryptoknowmics_html_stripper():
    html = "<div><p>Hello <b>World</b>!</p>&amp; More content</div>"
    text = remove_tags(html)
    assert "Hello World!" in text
    assert "& More content" in text
    assert "<" not in text and ">" not in text

    assert remove_tags("") == ""
    assert remove_tags(None) == ""


def test_cryptoknowmics_intake_creates_tasks():
    fake_api_response = {
        "responseData": [
            [],
            [],
            [
                {
                    "id": "ck-1",
                    "post_title": "Solana Performance Highlights",
                    "post_description": "<p>Network throughput achieves milestone.</p>",
                    "post_date": "2026-10-08",
                    "first_name": "Bob",
                    "last_name": "Smith",
                    "slug": "solana-milestone-2026"
                }
            ]
        ]
    }

    recorded_posts = []

    def mock_post(url, **kwargs):
        recorded_posts.append((url, kwargs))
        res = MagicMock()
        if "cryptoknowmics.com" in url:
            res.raise_for_status.return_value = None
            res.json.return_value = fake_api_response
            res.status_code = 200
        elif "/v1/tasks" in url:
            res.status_code = 201
        return res

    with patch("requests.post", side_effect=mock_post):
        fetch_cryptoknowmics("http://127.0.0.1:8080", "ck-hub-token")

    # 1 external API fetch + 1 internal task creation
    assert len(recorded_posts) == 2
    task_call = recorded_posts[1]
    task_payload = task_call[1]["json"]
    assert task_payload["adapter"] == "local_json_delivery"
    assert task_payload["params"]["title"] == "Solana Performance Highlights"
    assert task_payload["params"]["author"] == "Bob Smith"
    assert task_payload["params"]["content_text"] == "Network throughput achieves milestone."
    assert "solana-milestone-2026" in task_payload["params"]["url"]
    expected_hash = hashlib.sha256("https://www.cryptoknowmics.com/news/solana-milestone-2026".encode("utf-8")).hexdigest()
    assert task_payload["idempotency_key"] == f"cryptoknowmics:{expected_hash}"


def test_cryptoknowmics_intake_empty_posts():
    empty_response = {"responseData": []}
    recorded_posts = []

    def mock_post(url, **kwargs):
        recorded_posts.append((url, kwargs))
        res = MagicMock()
        res.raise_for_status.return_value = None
        res.json.return_value = empty_response
        return res

    with patch("requests.post", side_effect=mock_post):
        fetch_cryptoknowmics("http://127.0.0.1:8080", "ck-hub-token")

    # Only external API fetch was performed, no task created
    assert len(recorded_posts) == 1
