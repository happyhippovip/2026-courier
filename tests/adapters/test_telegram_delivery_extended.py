import pytest
from unittest.mock import MagicMock, patch
from courier_adapters.telegram_delivery import deliver

class BreakLoop(BaseException):
    pass

def test_telegram_delivery_missing_article_id():
    mock_post = MagicMock()
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-tel-1",
            "dispatch_id": "dsp-tel-1",
            "spec": {
                "adapter": "telegram_delivery",
                "params": {}, # missing article_id
            },
        }
    }
    start_resp = MagicMock(status_code=200, ok=True)

    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        claim_resp,                 # claim
        start_resp,                 # start
        MagicMock(status_code=200), # result failure
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            deliver("http://test-hub", "token", "w-1", "bot123", "chat456")

    res_call = mock_post.call_args_list[3]
    assert res_call[0][0] == "http://test-hub/v1/result"
    assert res_call[1]["json"]["outcome"] == "failure"
    assert res_call[1]["json"]["reason"] == "missing article_id"

def test_telegram_delivery_success_and_truncation():
    mock_post = MagicMock()
    huge_content = "important text " * 400 # > 4000 chars
    params = {
        "article_id": "art-huge",
        "title": "Mega Update",
        "author": "Alice",
        "published_at": "2026-10-09",
        "content_text": huge_content,
        "url": "https://example.com/art",
    }
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-tel-2",
            "dispatch_id": "dsp-tel-2",
            "spec": {
                "adapter": "telegram_delivery",
                "params": params,
            },
        }
    }
    start_resp = MagicMock(status_code=200, ok=True)
    tel_success = MagicMock(status_code=200, ok=True)

    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        claim_resp,                 # claim
        start_resp,                 # start
        tel_success,                # telegram API sendMessage
        MagicMock(status_code=200), # result success
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            deliver("http://test-hub", "token", "w-1", "bot123", "chat456")

    # Verify telegram call
    tel_call = mock_post.call_args_list[3]
    assert tel_call[0][0] == "https://api.telegram.org/botbot123/sendMessage"
    sent_text = tel_call[1]["json"]["text"]
    assert sent_text.endswith("... (truncated)")
    assert tel_call[1]["json"]["chat_id"] == "chat456"

    # Verify result call
    res_call = mock_post.call_args_list[4]
    assert res_call[0][0] == "http://test-hub/v1/result"
    assert res_call[1]["json"]["outcome"] == "success"
    assert res_call[1]["json"]["result_id"] == "res-art-huge"

def test_telegram_delivery_api_failure():
    mock_post = MagicMock()
    params = {
        "article_id": "art-fail",
        "title": "Short Update",
        "content_text": "Sample text",
    }
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-tel-3",
            "dispatch_id": "dsp-tel-3",
            "spec": {
                "adapter": "telegram_delivery",
                "params": params,
            },
        }
    }
    start_resp = MagicMock(status_code=200, ok=True)
    tel_fail = MagicMock(status_code=403, ok=False, text="Forbidden: bot was blocked by the user")

    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        claim_resp,                 # claim
        start_resp,                 # start
        tel_fail,                   # telegram API failure
        MagicMock(status_code=200), # result reporting failure
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            deliver("http://test-hub", "token", "w-1", "bot123", "chat456")

    # Verify failure reported to hub
    res_call = mock_post.call_args_list[4]
    assert res_call[0][0] == "http://test-hub/v1/result"
    assert res_call[1]["json"]["outcome"] == "failure"
    assert res_call[1]["json"]["reason"] == "telegram_403"
    assert res_call[1]["json"]["result_id"] == "res-art-fail-fail"
