import pytest
import json
import os
from scripts.revenue_customer_intake import submit_intake

def test_submit_intake_success(monkeypatch):
    import scripts.revenue_customer_intake as script
    
    posted_payload = []
    class MockResponse:
        status_code = 200
        text = "OK"
        
    def mock_post(url, json, headers):
        posted_payload.append(json)
        return MockResponse()
        
    monkeypatch.setattr(script.requests, "post", mock_post)
    
    submit_intake("test-owner", "test-repo", "abc1234", "CUST-001")
    
    assert len(posted_payload) == 1
    payload = posted_payload[0]
    
    assert "Revenue Safety Audit for test-owner/test-repo" in payload["goal_text"]
    assert len(payload["workflow_plan"]) == 1
    
    plan = payload["workflow_plan"][0]
    assert plan["type"] == "revenue_safety_audit"
    assert plan["target_agent"] == "linux"
    assert plan["target_owner"] == "test-owner"
    assert plan["target_repo"] == "test-repo"
    assert plan["target_sha"] == "abc1234"
    assert plan["customer_reference"] == "CUST-001"

def test_submit_intake_failure(monkeypatch, capfd):
    import scripts.revenue_customer_intake as script
    
    class MockResponse:
        status_code = 500
        text = "Internal Server Error"
        
    def mock_post(url, json, headers):
        return MockResponse()
        
    monkeypatch.setattr(script.requests, "post", mock_post)
    
    submit_intake("test-owner", "test-repo", "abc1234", "CUST-002")
    
    out, err = capfd.readouterr()
    assert "Failed: 500 Internal Server Error" in out
