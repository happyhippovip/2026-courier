import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from courier_adapters.local_json_delivery import deliver

class BreakLoop(BaseException):
    pass

def test_local_json_delivery_missing_article_id(tmp_path):
    mock_post = MagicMock()
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-json-1",
            "dispatch_id": "dsp-json-1",
            "spec": {
                "adapter": "local_json_delivery",
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
            deliver("http://test-hub", "token", "w-1")

    res_call = mock_post.call_args_list[3]
    assert res_call[0][0] == "http://test-hub/v1/result"
    assert res_call[1]["json"]["outcome"] == "failure"
    assert res_call[1]["json"]["reason"] == "missing article_id"

def test_local_json_delivery_success(tmp_path):
    mock_post = MagicMock()
    article_params = {
        "article_id": "art-local-123",
        "title": "Local JSON Title",
        "content_text": "Sample article content",
    }
    claim_resp = MagicMock(status_code=200, ok=True)
    claim_resp.json.return_value = {
        "task": {
            "task_id": "t-json-2",
            "dispatch_id": "dsp-json-2",
            "spec": {
                "adapter": "local_json_delivery",
                "params": article_params,
            },
        }
    }
    start_resp = MagicMock(status_code=200, ok=True)

    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        claim_resp,                 # claim
        start_resp,                 # start
        MagicMock(status_code=200), # result success
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            deliver("http://test-hub", "token", "w-1")

    # Verify file was written
    out_file = Path("delivered_articles") / "art-local-123.json"
    assert out_file.exists()
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved == article_params

    # Verify success reported
    res_call = mock_post.call_args_list[3]
    assert res_call[0][0] == "http://test-hub/v1/result"
    assert res_call[1]["json"]["outcome"] == "success"
    assert res_call[1]["json"]["result_id"] == "res-art-local-123"
    assert len(res_call[1]["json"]["artifacts"]) == 1

    # Cleanup
    if out_file.exists():
        out_file.unlink()

def test_local_json_delivery_204_and_other_adapter():
    mock_post = MagicMock()
    # 1. heartbeat, 2. 204 claim
    # 3. heartbeat, 4. claim with other adapter
    # 5. BreakLoop
    resp_204 = MagicMock(status_code=204, ok=True)
    other_adapter_resp = MagicMock(status_code=200, ok=True)
    other_adapter_resp.json.return_value = {
        "task": {
            "task_id": "t-other",
            "spec": {"adapter": "other_adapter"},
        }
    }

    mock_post.side_effect = [
        MagicMock(status_code=200), # heartbeat
        resp_204,                   # 204
        MagicMock(status_code=200), # heartbeat
        other_adapter_resp,         # other adapter
        BreakLoop()
    ]

    with patch("requests.post", mock_post), patch("time.sleep", return_value=None):
        with pytest.raises(BreakLoop):
            deliver("http://test-hub", "token", "w-1")

    # /v1/start and /v1/result should NEVER have been called
    urls = [call[0][0] for call in mock_post.call_args_list]
    assert "http://test-hub/v1/start" not in urls
    assert "http://test-hub/v1/result" not in urls
