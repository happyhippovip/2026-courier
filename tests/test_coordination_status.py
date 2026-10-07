import pytest
from unittest.mock import patch, MagicMock
from scripts.coordination_ledger import CoordinationEvent, AgentID, HostID, EventType, MissionStatus
from scripts.coordination_status import main
import sys

@patch("scripts.coordination_status.GitHubCoordinationAdapter")
@patch("sys.stdout")
def test_coordination_status_cli(mock_stdout, mock_adapter_class):
    mock_adapter = MagicMock()
    mock_adapter.read_events.return_value = [
        CoordinationEvent(
            event_id="1",
            mission_id="m1",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=[],
            head="sha1",
            evidence_ref="ref1",
            created_at="2026-10-07T12:00:00Z",
            payload_hash="abc"
        )
    ]
    mock_adapter_class.return_value = mock_adapter
    
    with patch.object(sys, "argv", ["coordination_status.py", "--repo", "test/repo", "--issue", "1"]):
        main()
        
    mock_adapter_class.assert_called_once_with("test/repo", 1)
    mock_adapter.read_events.assert_called_once()
