import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from courier_adapters.local_json_delivery import deliver

@patch('requests.post')
@patch('time.sleep', side_effect=InterruptedError)
def test_local_json_delivery(mock_sleep, mock_post, tmp_path):
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

    with patch('courier_adapters.local_json_delivery.Path') as mock_path:
        mock_path.return_value = tmp_path
        
        try:
            deliver("http://fake-hub", "fake-token", "worker-1")
        except InterruptedError:
            pass

    # Verify file was written
    expected_path = tmp_path / "art-1.json"
    assert expected_path.exists()
    
    with open(expected_path, "r", encoding="utf-8") as f:
        parsed = json.load(f)
        
    assert parsed["article_id"] == "art-1"
    assert parsed["title"] == "Test Delivery"

    import hashlib
    with open(expected_path, "rb") as f:
        real_hash = hashlib.sha256(f.read()).hexdigest()

    # Verify result was success
    result_call = next((call for call in mock_post.call_args_list if "/v1/result" in call[0][0]), None)
    assert result_call is not None
    assert result_call[1]['json']['outcome'] == 'success'
    assert result_call[1]['json']['artifacts'][0]['sha256'] == real_hash

