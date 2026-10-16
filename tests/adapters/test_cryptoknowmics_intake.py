import pytest
import requests
from unittest.mock import patch, MagicMock
from courier_adapters.cryptoknowmics_intake import fetch_cryptoknowmics, remove_tags

def test_remove_tags():
    html = "<p>Hello <b>world</b>!</p>"
    text = remove_tags(html)
    assert text == "Hello world!"

@patch('requests.post')
def test_fetch_cryptoknowmics(mock_post):
    # Mock the API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "responseData": [
            {}, # index 0
            {}, # index 1
            [   # index 2: posts array
                {
                    "id": "123",
                    "post_title": "Ethereum is booming",
                    "post_description": "<p>Content goes here</p>",
                    "post_date": "2026-01-01",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "slug": "eth-booming"
                }
            ]
        ]
    }
    mock_response.raise_for_status.return_value = None
    
    # We have two posts happening: one to the API, one to the hub
    # We will use a side_effect to distinguish them
    def side_effect(url, **kwargs):
        if url.startswith("https://www.cryptoknowmics.com"):
            return mock_response
        else:
            hub_res = MagicMock()
            hub_res.status_code = 201
            return hub_res

    mock_post.side_effect = side_effect

    fetch_cryptoknowmics("http://fake-hub", "fake-token")

    # Assert 2 post calls were made (1 for intake, 1 for hub)
    assert mock_post.call_count == 2
    
    # Check the hub call
    hub_call = mock_post.call_args_list[1]
    args, kwargs = hub_call
    assert args[0] == "http://fake-hub/v1/tasks"
    payload = kwargs['json']
    
    assert payload['adapter'] == 'local_json_delivery'
    assert payload['params']['title'] == 'Ethereum is booming'
    assert payload['params']['source_id'] == 'cryptoknowmics'
    assert payload['params']['author'] == 'Jane Doe'
    assert payload['params']['content_text'] == 'Content goes here'

