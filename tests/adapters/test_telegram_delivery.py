import pytest
import time
from unittest.mock import patch, MagicMock
from courier_adapters.telegram_delivery import deliver

@patch('requests.post')
@patch('time.sleep', side_effect=InterruptedError)
def test_telegram_delivery_success(mock_sleep, mock_post):
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
                        "adapter": "telegram_delivery",
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
        elif "api.telegram.org" in url:
            res.ok = True
        elif "/v1/result" in url:
            res.ok = True
        return res

    mock_post.side_effect = mock_post_side_effect

    try:
        deliver("http://fake-hub", "fake-token", "worker-1", "tel-token", "chat-id")
    except InterruptedError:
        pass

    # Verify telegram API was called
    tel_call = next((call for call in mock_post.call_args_list if "api.telegram.org" in call[0][0]), None)
    assert tel_call is not None, "Should have called Telegram API"
    assert tel_call[1]['json']['chat_id'] == "chat-id"
    assert "Test Delivery" in tel_call[1]['json']['text']

    # Verify result was success
    result_call = next((call for call in mock_post.call_args_list if "/v1/result" in call[0][0]), None)
    assert result_call is not None
    assert result_call[1]['json']['outcome'] == 'success'

