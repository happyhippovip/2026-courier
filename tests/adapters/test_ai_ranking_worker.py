import pytest
import time
from unittest.mock import patch, MagicMock
from courier_adapters.ai_ranking_worker import evaluate_and_route

@patch('requests.post')
@patch('time.sleep', side_effect=InterruptedError)  # To break the infinite loop after one iteration
def test_evaluate_and_route_relevant(mock_sleep, mock_post):
    # Mock responses
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
                        "adapter": "ai_ranking_worker",
                        "params": {
                            "title": "Bitcoin reaches new high",
                            "content_text": "The price of BTC is going up.",
                            "article_id": "art-1"
                        }
                    }
                }
            }
        elif "/v1/start" in url:
            res.ok = True
        elif "/v1/tasks" in url:
            res.ok = True
        elif "/v1/result" in url:
            res.ok = True
        return res

    mock_post.side_effect = mock_post_side_effect

    try:
        evaluate_and_route("http://fake-hub", "fake-token", "worker-1")
    except InterruptedError:
        pass

    # Verify that it routed to telegram because "bitcoin" is in title
    tasks_call = next((call for call in mock_post.call_args_list if "/v1/tasks" in call[0][0]), None)
    assert tasks_call is not None, "Should have created a new delivery task"
    
    payload = tasks_call[1]['json']
    assert payload['adapter'] == 'telegram_delivery'
    assert payload['idempotency_key'] == 'telegram:art-1'
    
    # Verify it completed the claim successfully
    result_call = next((call for call in mock_post.call_args_list if "/v1/result" in call[0][0]), None)
    assert result_call is not None
    assert result_call[1]['json']['outcome'] == 'success'

@patch('requests.post')
@patch('time.sleep', side_effect=InterruptedError)
def test_evaluate_and_route_irrelevant(mock_sleep, mock_post):
    def mock_post_side_effect(url, **kwargs):
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            res.ok = True
            res.json.return_value = {
                "task": {
                    "task_id": "test-task",
                    "dispatch_id": "disp-2",
                    "spec": {
                        "adapter": "ai_ranking_worker",
                        "params": {
                            "title": "Random news",
                            "content_text": "Nothing to do with crypto.",
                            "article_id": "art-2"
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

    try:
        evaluate_and_route("http://fake-hub", "fake-token", "worker-1")
    except InterruptedError:
        pass

    # Verify that it did NOT route to telegram
    tasks_call = next((call for call in mock_post.call_args_list if "/v1/tasks" in call[0][0]), None)
    assert tasks_call is None, "Should NOT have created a delivery task for irrelevant content"
    
    # Verify it completed the claim successfully and dropped
    result_call = next((call for call in mock_post.call_args_list if "/v1/result" in call[0][0]), None)
    assert result_call is not None
    assert result_call[1]['json']['outcome'] == 'success'
    assert "Dropped" in result_call[1]['json']['reason']

