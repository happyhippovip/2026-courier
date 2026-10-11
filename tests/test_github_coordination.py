from scripts.github_coordination import GitHubCoordinationAdapter
from scripts.coordination_ledger import CoordinationEvent, AgentID, HostID, EventType, MissionStatus
from unittest.mock import patch, MagicMock

@patch("requests.get")
@patch("requests.post")
def test_github_adapter_read_write(mock_post, mock_get):
    adapter = GitHubCoordinationAdapter("test/repo", 1, "token")
    
    # Test read
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "body": "Comment body\n```json\n{\"event_id\": \"123\", \"mission_id\": \"m1\", \"agent_id\": \"GOOGLE_WINDOWS\", \"host_id\": \"WINDOWS_REMOTE\", \"event_type\": \"ASSIGNED\", \"status\": \"WORKING\", \"depends_on\": [], \"head\": null, \"evidence_ref\": \"ref1\", \"created_at\": \"2026-10-07T12:00:00Z\", \"payload_hash\": \"abc\"}\n```"
        }
    ]
    mock_get.return_value = mock_response
    
    events = adapter.read_events()
    assert len(events) == 1
    assert events[0].mission_id == "m1"
    assert events[0].agent_id == AgentID.GOOGLE_WINDOWS
    
    # Test write
    mock_post_response = MagicMock()
    mock_post_response.status_code = 201
    mock_post.return_value = mock_post_response
    
    success = adapter.write_event(events[0])
    assert success is True
    mock_post.assert_called_once()
