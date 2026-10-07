import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from courier_adapters.local_json_delivery import deliver

@patch('requests.post')
@patch('time.sleep', side_effect=InterruptedError)
@patch('builtins.open')
@patch('pathlib.Path.mkdir')
def test_local_json_delivery(mock_mkdir, mock_open, mock_sleep, mock_post):
    def mock_post_side_effect(url, **kwargs):
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            res.ok = True
            res.json.return_value = {
                "task": {
                    "task_id": "test-task",
                    "dispatch_id": "disp-1",
                    "spec": {
                        "adapter": "local_json_delivery",
                        "params": {
                            "title": "Test Delivery",
                            "content_text": "Content",
                            "article_id": "art-1"
                        }
                    }
                }
            }
        elif "/v1/start" in url:
            res.ok = True
        elif "/v1/result" in url:
            res.ok = True
        return res

    mock_post.side_effect = mock_post_side_effect

    mock_file = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_file

    try:
        deliver("http://fake-hub", "fake-token", "worker-1")
    except InterruptedError:
        pass

    # Verify file was opened and written
    expected_path = Path("delivered_articles") / "art-1.json"
    mock_open.assert_called_with(expected_path, "w", encoding="utf-8")
    
    # Check what was written
    written_data = "".join(call[0][0] for call in mock_file.write.call_args_list)
    parsed = json.loads(written_data)
    assert parsed["article_id"] == "art-1"
    assert parsed["title"] == "Test Delivery"

    # Verify result was success
    result_call = next((call for call in mock_post.call_args_list if "/v1/result" in call[0][0]), None)
    assert result_call is not None
    assert result_call[1]['json']['outcome'] == 'success'

