import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from courier_adapters.cryptoknowmics_intake import (
    HTMLStripper,
    remove_tags,
    fetch_cryptoknowmics,
)
from courier_adapters.decrypt_intake import fetch_decrypt


def test_remove_tags_edge_cases():
    # None or empty
    assert remove_tags(None) == ""
    assert remove_tags("") == ""
    assert remove_tags("   ") == ""

    # Plain text
    assert remove_tags("Hello world") == "Hello world"

    # HTML tags
    assert remove_tags("<p>Paragraph</p>") == "Paragraph"
    assert remove_tags("<b>Bold</b> and <i>Italic</i>") == "Bold and Italic"

    # Nested tags and attributes
    html = '<div class="content"><span style="color:red">Nested</span> <a href="http://example.com">Link</a></div>'
    assert remove_tags(html) == "Nested Link"

    # HTML entities
    assert remove_tags("Symphony &amp; Courier &gt; Legacy") == "Symphony & Courier > Legacy"


@patch("courier_adapters.decrypt_intake.requests.post")
@patch("courier_adapters.decrypt_intake.requests.get")
def test_fetch_decrypt_flow(mock_get, mock_post, capsys):
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <title>Decrypt Feed</title>
        <item>
          <title>Test Bitcoin Surge</title>
          <link>https://decrypt.co/test-surge-article</link>
          <pubDate>Thu, 08 Oct 2026 12:00:00 +0000</pubDate>
          <dc:creator>Alice Satoshi</dc:creator>
          <content:encoded><![CDATA[<p>Full article body with details</p>]]></content:encoded>
        </item>
      </channel>
    </rss>
    """
    mock_get_resp = MagicMock()
    mock_get_resp.content = rss_xml.encode("utf-8")
    mock_get.return_value = mock_get_resp

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 201
    mock_post.return_value = mock_post_resp

    fetch_decrypt("http://127.0.0.1:8080", "secret-token-123")

    mock_get.assert_called_once()
    mock_post.assert_called_once()

    # Check payload sent to Hub
    call_args, call_kwargs = mock_post.call_args
    assert call_args[0] == "http://127.0.0.1:8080/v1/tasks"
    assert call_kwargs["headers"] == {"X-Courier-Token": "secret-token-123"}

    payload = call_kwargs["json"]
    assert payload["adapter"] == "local_json_delivery"
    assert payload["effect_class"] == "idempotent"
    assert payload["max_attempts"] == 3
    assert payload["lease_ttl_s"] == 60

    expected_link = "https://decrypt.co/test-surge-article"
    expected_id = hashlib.sha256(expected_link.encode("utf-8")).hexdigest()
    assert payload["idempotency_key"] == f"decrypt:{expected_id}"

    article = payload["params"]
    assert article["article_id"] == expected_id
    assert article["title"] == "Test Bitcoin Surge"
    assert article["author"] == "Alice Satoshi"
    assert "Full article body with details" in article["content_text"]

    captured = capsys.readouterr()
    assert f"Created task for {expected_id}" in captured.out


@patch("courier_adapters.cryptoknowmics_intake.requests.post")
def test_fetch_cryptoknowmics_flow(mock_post, capsys):
    api_response = {
        "responseData": [
            "placeholder0",
            "placeholder1",
            [
                {
                    "id": "ck-101",
                    "post_title": "Ethereum Layer 2 Upgrades",
                    "post_description": "<p>Vitalik announced <b>huge</b> throughput improvements.</p>",
                    "post_date": "2026-10-08",
                    "first_name": "Bob",
                    "last_name": "Developer",
                    "slug": "eth-layer2-upgrades",
                }
            ],
        ]
    }

    # First POST is the external API call; second POST is to Courier Hub
    mock_api_resp = MagicMock()
    mock_api_resp.json.return_value = api_response

    mock_hub_resp = MagicMock()
    mock_hub_resp.status_code = 200  # Duplicate skip

    mock_post.side_effect = [mock_api_resp, mock_hub_resp]

    fetch_cryptoknowmics("http://127.0.0.1:8080", "hub-token-456")

    assert mock_post.call_count == 2

    hub_call = mock_post.call_args_list[1]
    assert hub_call[0][0] == "http://127.0.0.1:8080/v1/tasks"
    assert hub_call[1]["headers"] == {"X-Courier-Token": "hub-token-456"}

    payload = hub_call[1]["json"]
    expected_link = "https://www.cryptoknowmics.com/news/eth-layer2-upgrades"
    expected_id = hashlib.sha256(expected_link.encode("utf-8")).hexdigest()
    assert payload["idempotency_key"] == f"cryptoknowmics:{expected_id}"

    article = payload["params"]
    assert article["author"] == "Bob Developer"
    assert article["content_text"] == "Vitalik announced huge throughput improvements."

    captured = capsys.readouterr()
    assert f"Skipped duplicate {expected_id}" in captured.out
