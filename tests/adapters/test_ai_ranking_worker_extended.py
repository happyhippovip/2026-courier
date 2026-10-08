import pytest
from unittest.mock import MagicMock, patch
from courier_adapters.ai_ranking_worker import evaluate_and_route

class BreakLoop(BaseException):
    pass

def test_ai_ranking_empty_content_failure():
    mock_post = MagicMock()
    # 1. heartbeat, 2. claim -> returns task with empty content
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-1",
            "dispatch_id": "dsp-1",
            "spec": {
                "adapter": "ai_ranking_worker",
                "params": {"title": "", "content_text": ""},
            },
        }
    }
    start_resp = MagicMock(status_code=200, ok=True)
    
    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        claim_resp,                 # claim
        start_resp,                 # start
        MagicMock(status_code=200), # result (failure)
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            evaluate_and_route("http://test-hub", "token", "w-1")

    # Verify result reported failure with "Empty content"
    result_call = mock_post.call_args_list[3]
    assert result_call[0][0] == "http://test-hub/v1/result"
    assert result_call[1]["json"]["outcome"] == "failure"
    assert result_call[1]["json"]["reason"] == "Empty content"

def test_ai_ranking_high_relevance_routes_to_telegram():
    mock_post = MagicMock()
    article_params = {
        "article_id": "art-btc-1",
        "title": "Bitcoin reaches new milestone",
        "content_text": "The SEC has commented on regulation and Ethereum adoption.",
    }
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-btc",
            "dispatch_id": "dsp-btc",
            "spec": {
                "adapter": "ai_ranking_worker",
                "params": article_params,
            },
        }
    }
    start_resp = MagicMock(status_code=200, ok=True)
    task_create_resp = MagicMock(status_code=201, ok=True)

    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        claim_resp,                 # claim
        start_resp,                 # start
        task_create_resp,           # route to telegram task
        MagicMock(status_code=200), # result
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            evaluate_and_route("http://test-hub", "token", "w-1")

    # Check routing task
    route_call = mock_post.call_args_list[3]
    assert route_call[0][0] == "http://test-hub/v1/tasks"
    route_payload = route_call[1]["json"]
    assert route_payload["adapter"] == "telegram_delivery"
    assert route_payload["effect_class"] == "idempotent"
    assert route_payload["idempotency_key"] == "telegram:art-btc-1"
    assert route_payload["params"] == article_params

    # Check result call
    res_call = mock_post.call_args_list[4]
    assert res_call[0][0] == "http://test-hub/v1/result"
    assert res_call[1]["json"]["outcome"] == "success"

def test_ai_ranking_low_relevance_dropped():
    mock_post = MagicMock()
    article_params = {
        "article_id": "art-recipe-1",
        "title": "Best Apple Pie Recipe",
        "content_text": "Here is how you bake cinnamon apples in autumn.",
    }
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-pie",
            "dispatch_id": "dsp-pie",
            "spec": {
                "adapter": "ai_ranking_worker",
                "params": article_params,
            },
        }
    }
    start_resp = MagicMock(status_code=200, ok=True)

    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        claim_resp,                 # claim
        start_resp,                 # start
        MagicMock(status_code=200), # result dropped
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            evaluate_and_route("http://test-hub", "token", "w-1")

    # Should NOT post to /v1/tasks, only to /v1/result
    urls_called = [call[0][0] for call in mock_post.call_args_list]
    assert "http://test-hub/v1/tasks" not in urls_called
    res_call = mock_post.call_args_list[3]
    assert res_call[0][0] == "http://test-hub/v1/result"
    assert res_call[1]["json"]["outcome"] == "success"
    assert res_call[1]["json"]["reason"] == "Dropped due to low score"
