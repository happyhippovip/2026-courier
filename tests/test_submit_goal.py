import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import submit_goal

def test_submit_goal_text(capsys):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    
    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        submit_goal.submit_goal(goal_text="Test goal")
        
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "goals" in args[0]
    
    payload = kwargs["json"]
    assert "GOAL-" in payload["goal_id"]
    assert payload["goal_text"] == "Test goal"
    
    captured = capsys.readouterr()
    assert "Successfully submitted" in captured.out

def test_submit_goal_json_file(tmp_path, capsys):
    json_file = tmp_path / "goal.json"
    json_file.write_text(json.dumps({"goal_text": "From file"}))
    
    mock_response = mock.Mock()
    mock_response.status_code = 200
    
    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        submit_goal.submit_goal(json_file=str(json_file))
        
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]
    assert "GOAL-" in payload["goal_id"]
    assert payload["goal_text"] == "From file"

def test_submit_goal_json_file_with_id(tmp_path, capsys):
    json_file = tmp_path / "goal.json"
    json_file.write_text(json.dumps({"goal_id": "CUSTOM-123", "goal_text": "From file"}))
    
    mock_response = mock.Mock()
    mock_response.status_code = 200
    
    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        submit_goal.submit_goal(json_file=str(json_file))
        
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]
    assert payload["goal_id"] == "CUSTOM-123"

def test_submit_goal_failure(capsys):
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.text = "Server error"
    
    with mock.patch("requests.post", return_value=mock_response) as mock_post:
        submit_goal.submit_goal(goal_text="Test goal")
        
    captured = capsys.readouterr()
    assert "API Error: 500" in captured.out

def test_submit_goal_exception(capsys):
    with mock.patch("requests.post", side_effect=Exception("Connection refused")) as mock_post:
        submit_goal.submit_goal(goal_text="Test goal")
        
    captured = capsys.readouterr()
    assert "Could not connect to" in captured.out

