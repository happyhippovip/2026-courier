import os
import sys
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import revenue_customer_intake

def test_submit_intake_success(capsys):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    
    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        revenue_customer_intake.submit_intake("testowner", "testrepo", "123abcsha", "cust_123")
        
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "goals" in args[0]
    
    payload = kwargs["json"]
    assert "REVENUE-GOAL" in payload["goal_id"]
    assert payload["workflow_plan"][0]["target_owner"] == "testowner"
    assert payload["workflow_plan"][0]["target_repo"] == "testrepo"
    assert payload["workflow_plan"][0]["target_sha"] == "123abcsha"
    assert payload["workflow_plan"][0]["customer_reference"] == "cust_123"
    
    captured = capsys.readouterr()
    assert "Success!" in captured.out

def test_submit_intake_failure(capsys):
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    with mock.patch("requests.post", return_value=mock_response):
        revenue_customer_intake.submit_intake("testowner", "testrepo", "123abcsha", "cust_123")
        
    captured = capsys.readouterr()
    assert "Failed: 500 Internal Server Error" in captured.out

