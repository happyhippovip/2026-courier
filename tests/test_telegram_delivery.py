import json
import pytest
from unittest.mock import MagicMock, patch

from courier_adapters.telegram_delivery import deliver


class StopDeliveryLoop(KeyboardInterrupt):
    """Exception to break worker while-True loop deterministically."""
    pass


def test_telegram_delivery_success():
    recorded_calls = []
    claim_count = 0

    def mock_post(url, **kwargs):
        nonlocal claim_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            claim_count += 1
            if claim_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-tel-1",
                        "dispatch_id": "disp-tel-1",
                        "spec": {
                            "adapter": "telegram_delivery",
                            "params": {
                                "article_id": "art-999",
                                "title": "Ethereum 2026 Milestone",
                                "author": "Alice",
                                "published_at": "2026-10-08",
                                "content_text": "Vitalik details the roadmap for state proofs.",
                                "url": "https://example.com/eth-2026",
                            },
                        },
                    }
                }
            else:
                raise StopDeliveryLoop("done")
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "api.telegram.org" in url:
            res.ok = True
            res.status_code = 200
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopDeliveryLoop):
            deliver("http://127.0.0.1:8080", "hub-token", "tel-worker-1", "fake-bot-token", "123456")

    # 1. Telegram API call check
    tel_call = next((c for c in recorded_calls if "api.telegram.org" in c[0]), None)
    assert tel_call is not None
    payload = tel_call[1]["json"]
    assert payload["chat_id"] == "123456"
    assert "Ethereum 2026 Milestone" in payload["text"]
    assert "Alice" in payload["text"]
    assert payload["parse_mode"] == "Markdown"

    # 2. Hub result check
    result_call = next((c for c in recorded_calls if "/v1/result" in c[0]), None)
    assert result_call is not None
    res_payload = result_call[1]["json"]
    assert res_payload["outcome"] == "success"
    assert res_payload["dispatch_id"] == "disp-tel-1"
    assert res_payload["result_id"] == "res-art-999"


def test_telegram_delivery_api_failure():
    recorded_calls = []
    claim_count = 0

    def mock_post(url, **kwargs):
        nonlocal claim_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            claim_count += 1
            if claim_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-tel-2",
                        "dispatch_id": "disp-tel-2",
                        "spec": {
                            "adapter": "telegram_delivery",
                            "params": {
                                "article_id": "art-failed-api",
                                "title": "Test Title",
                            },
                        },
                    }
                }
            else:
                raise StopDeliveryLoop("done")
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "api.telegram.org" in url:
            res.ok = False
            res.status_code = 403
            res.text = "Forbidden: bot was blocked by the user"
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopDeliveryLoop):
            deliver("http://127.0.0.1:8080", "hub-token", "tel-worker-1", "fake-bot-token", "123456")

    result_call = next((c for c in recorded_calls if "/v1/result" in c[0]), None)
    assert result_call is not None
    res_payload = result_call[1]["json"]
    assert res_payload["outcome"] == "failure"
    assert "telegram_403" in res_payload["reason"]


def test_telegram_delivery_missing_article_id():
    recorded_calls = []
    claim_count = 0

    def mock_post(url, **kwargs):
        nonlocal claim_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            claim_count += 1
            if claim_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-tel-3",
                        "dispatch_id": "disp-tel-3",
                        "spec": {
                            "adapter": "telegram_delivery",
                            "params": {
                                "title": "Missing article id",
                            },
                        },
                    }
                }
            else:
                raise StopDeliveryLoop("done")
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopDeliveryLoop):
            deliver("http://127.0.0.1:8080", "hub-token", "tel-worker-1", "fake-bot-token", "123456")

    # Should NOT attempt Telegram API call
    assert not any("api.telegram.org" in c[0] for c in recorded_calls)

    result_call = next((c for c in recorded_calls if "/v1/result" in c[0]), None)
    assert result_call is not None
    res_payload = result_call[1]["json"]
    assert res_payload["outcome"] == "failure"
    assert res_payload["reason"] == "missing article_id"


def test_telegram_delivery_truncates_long_messages():
    recorded_calls = []
    claim_count = 0

    def mock_post(url, **kwargs):
        nonlocal claim_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            claim_count += 1
            if claim_count == 1:
                res.ok = True
                res.status_code = 200
                res.json.return_value = {
                    "task": {
                        "task_id": "task-tel-4",
                        "dispatch_id": "disp-tel-4",
                        "spec": {
                            "adapter": "telegram_delivery",
                            "params": {
                                "article_id": "art-long",
                                "title": "Massive post",
                                "content_text": "X" * 6000,
                            },
                        },
                    }
                }
            else:
                raise StopDeliveryLoop("done")
        elif "/v1/start" in url:
            res.ok = True
            res.status_code = 200
        elif "api.telegram.org" in url:
            res.ok = True
            res.status_code = 200
        elif "/v1/result" in url:
            res.ok = True
            res.status_code = 200
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopDeliveryLoop):
            deliver("http://127.0.0.1:8080", "hub-token", "tel-worker-1", "fake-bot-token", "123456")

    tel_call = next((c for c in recorded_calls if "api.telegram.org" in c[0]), None)
    assert tel_call is not None
    text = tel_call[1]["json"]["text"]
    assert len(text) <= 4020
    assert text.endswith("... (truncated)")


def test_telegram_delivery_claim_204_sleeps():
    claim_count = 0
    recorded_calls = []

    def mock_post(url, **kwargs):
        nonlocal claim_count
        recorded_calls.append((url, kwargs))
        res = MagicMock()
        if "/v1/heartbeat" in url:
            res.status_code = 200
        elif "/v1/claim" in url:
            claim_count += 1
            if claim_count == 1:
                res.status_code = 204
            else:
                raise StopDeliveryLoop("done")
        return res

    with patch("requests.post", side_effect=mock_post), patch("time.sleep"):
        with pytest.raises(StopDeliveryLoop):
            deliver("http://127.0.0.1:8080", "hub-token", "tel-worker-1", "fake-bot-token", "123456")

    assert not any("/v1/start" in c[0] for c in recorded_calls)
