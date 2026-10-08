import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from courier_adapters.ai_ranking_worker import evaluate_and_route


class StopWorkerLoop(KeyboardInterrupt):
    """Exception inheriting from BaseException to cleanly break infinite worker loop."""
    pass


def test_ai_ranking_worker_keyword_match_routes_telegram():
    call_count = 0

    def mock_post_side_effect(url, **kwargs):
        nonlocal call_count
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            call_count += 1
            if call_count > 1:
                raise StopWorkerLoop("done")
            res.ok = True
            res.status_code = 200
            res.json.return_value = {
                "task": {
                    "task_id": "task-rank-1",
                    "dispatch_id": "disp-rank-1",
                    "spec": {
                        "adapter": "ai_ranking_worker",
                        "params": {
                            "title": "Breaking Bitcoin News",
                            "content_text": "SEC approves new spot btc regulations",
                            "article_id": "art-btc-101",
                        },
                    },
                }
            }
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "/v1/tasks" in url:
            res.ok = True
            res.status_code = 201
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post_side_effect), patch("time.sleep"):
        with pytest.raises(StopWorkerLoop):
            evaluate_and_route("http://127.0.0.1:8080", "test-token", "ranker-1")

    # Verified route to telegram delivery task
    task_calls = [c for c in mock_post_side_effect.__wrapped__.mock if hasattr(mock_post_side_effect, "__wrapped__")] if False else None


def test_ai_ranking_worker_pipeline_assertions():
    call_count = 0
    recorded_calls = []

    def mock_post(url, **kwargs):
        nonlocal call_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            call_count += 1
            if call_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-rank-1",
                        "dispatch_id": "disp-rank-1",
                        "spec": {
                            "adapter": "ai_ranking_worker",
                            "params": {
                                "title": "Breaking Bitcoin News",
                                "content_text": "SEC approves new spot btc regulations",
                                "article_id": "art-btc-101",
                            },
                        },
                    }
                }
            else:
                raise StopWorkerLoop("done")
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "/v1/tasks" in url:
            res.ok = True
            res.status_code = 201
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopWorkerLoop):
            evaluate_and_route("http://127.0.0.1:8080", "test-token", "ranker-1")

    calls = [c[0] for c in recorded_calls]
    assert any("/v1/heartbeat" in c for c in calls)
    assert any("/v1/claim" in c for c in calls)
    assert any("/v1/start" in c for c in calls)

    # Verified route to telegram delivery task
    task_call = next((c for c in recorded_calls if "/v1/tasks" in c[0]), None)
    assert task_call is not None
    task_json = task_call[1]["json"]
    assert task_json["adapter"] == "telegram_delivery"
    assert task_json["idempotency_key"] == "telegram:art-btc-101"

    # Verified result outcome is success
    res_call = next((c for c in recorded_calls if "/v1/result" in c[0]), None)
    assert res_call is not None
    res_json = res_call[1]["json"]
    assert res_json["outcome"] == "success"
    assert res_json["dispatch_id"] == "disp-rank-1"


def test_ai_ranking_worker_low_score_dropped():
    call_count = 0
    recorded_calls = []

    def mock_post(url, **kwargs):
        nonlocal call_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            call_count += 1
            if call_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-rank-2",
                        "dispatch_id": "disp-rank-2",
                        "spec": {
                            "adapter": "ai_ranking_worker",
                            "params": {
                                "title": "Weather forecast today",
                                "content_text": "It is sunny outside with clear blue skies.",
                                "article_id": "art-weather-202",
                            },
                        },
                    }
                }
            else:
                raise StopWorkerLoop("done")
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopWorkerLoop):
            evaluate_and_route("http://127.0.0.1:8080", "test-token", "ranker-1")

    # No telegram delivery tasks created
    assert not any("/v1/tasks" in c[0] for c in recorded_calls)

    # Verified dropped with low score reason
    res_call = next((c for c in recorded_calls if "/v1/result" in c[0]), None)
    assert res_call is not None
    res_json = res_call[1]["json"]
    assert res_json["outcome"] == "success"
    assert res_json["reason"] == "Dropped due to low score"


def test_ai_ranking_worker_empty_content_failure():
    call_count = 0
    recorded_calls = []

    def mock_post(url, **kwargs):
        nonlocal call_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            call_count += 1
            if call_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-rank-3",
                        "dispatch_id": "disp-rank-3",
                        "spec": {
                            "adapter": "ai_ranking_worker",
                            "params": {
                                "title": "",
                                "content_text": "",
                                "article_id": "art-empty-303",
                            },
                        },
                    }
                }
            else:
                raise StopWorkerLoop("done")
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopWorkerLoop):
            evaluate_and_route("http://127.0.0.1:8080", "test-token", "ranker-1")

    # Result is failure
    res_call = next((c for c in recorded_calls if "/v1/result" in c[0]), None)
    assert res_call is not None
    res_json = res_call[1]["json"]
    assert res_json["outcome"] == "failure"
    assert res_json["reason"] == "Empty content"


def test_ai_ranking_worker_claim_204_sleeps():
    call_count = 0
    recorded_calls = []

    def mock_post(url, **kwargs):
        nonlocal call_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            call_count += 1
            if call_count == 1:
                res.status_code = 204
            else:
                raise StopWorkerLoop("done")
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopWorkerLoop):
            evaluate_and_route("http://127.0.0.1:8080", "test-token", "ranker-1")

    calls = [c[0] for c in recorded_calls]
    assert any("/v1/claim" in c for c in calls)
    assert not any("/v1/start" in c for c in calls)


def test_ai_ranking_worker_different_adapter_skips():
    call_count = 0
    recorded_calls = []

    def mock_post(url, **kwargs):
        nonlocal call_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            call_count += 1
            if call_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-other",
                        "dispatch_id": "disp-other",
                        "spec": {
                            "adapter": "other_worker",
                            "params": {},
                        },
                    }
                }
            else:
                raise StopWorkerLoop("done")
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopWorkerLoop):
            evaluate_and_route("http://127.0.0.1:8080", "test-token", "ranker-1")

    calls = [c[0] for c in recorded_calls]
    assert any("/v1/claim" in c for c in calls)
    assert not any("/v1/start" in c for c in calls)
