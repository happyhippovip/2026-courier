import requests
from unittest.mock import patch
import scripts.revenue_customer_intake as rci

def test_submit_intake():
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        rci.submit_intake("test", "repo", "sha", "ref")
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert "workflow_plan" in payload
        assert "tasks" not in payload
