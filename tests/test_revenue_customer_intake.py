import pytest
from unittest.mock import MagicMock
import scripts.revenue_customer_intake as intake

def test_revenue_customer_intake_payload(monkeypatch):
    mock_post = MagicMock()
    # mock response
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_post.return_value = mock_res
    monkeypatch.setattr(intake.requests, "post", mock_post)

    intake.submit_intake("myowner", "myrepo", "mysha", "myref")

    assert mock_post.called
    kwargs = mock_post.call_args[1]
    payload = kwargs["json"]
    
    assert "goal_text" in payload
    assert "workflow_plan" in payload
    assert "tasks" not in payload
    
    plan = payload["workflow_plan"]
    assert len(plan) == 1
    step = plan[0]
    
    assert step["type"] == "revenue_safety_audit"
    assert step["target_owner"] == "myowner"
    assert step["target_repo"] == "myrepo"
    assert step["target_sha"] == "mysha"
    assert step["customer_reference"] == "myref"
    assert step["capabilities"] == ["revenue_safety_audit"]
