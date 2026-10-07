import pytest
import requests
from unittest.mock import patch, MagicMock
from courier_adapters.decrypt_intake import fetch_decrypt

@patch('requests.get')
@patch('requests.post')
def test_fetch_decrypt(mock_post, mock_get):
    # Mock the RSS feed response
    mock_response = MagicMock()
    mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel>
        <item>
            <title>Test Crypto News</title>
            <link>https://decrypt.co/1234/test-news</link>
            <pubDate>Mon, 01 Jan 2026 12:00:00 +0000</pubDate>
            <dc:creator>John Doe</dc:creator>
            <content:encoded><![CDATA[<p>Bitcoin is great</p>]]></content:encoded>
        </item>
    </channel>
</rss>
"""
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # Mock the Hub POST response
    mock_hub_res = MagicMock()
    mock_hub_res.status_code = 201
    mock_post.return_value = mock_hub_res

    fetch_decrypt("http://fake-hub", "fake-token")

    # Assert get was called
    mock_get.assert_called_once_with('https://decrypt.co/feed', headers={'User-Agent': 'Mozilla/5.0'})
    
    # Assert post was called with correct task payload
    assert mock_post.called
    call_args = mock_post.call_args[1]
    assert call_args['headers'] == {'X-Courier-Token': 'fake-token'}
    
    payload = call_args['json']
    assert payload['adapter'] == 'local_json_delivery'
    assert payload['params']['title'] == 'Test Crypto News'
    assert payload['params']['source_id'] == 'decrypt'
    assert payload['params']['author'] == 'John Doe'
    assert payload['params']['content_text'] == '<p>Bitcoin is great</p>'

