import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.revenue_outreach import ExternalEmailConnector
from courier_runtime.revenue import Lead, CONTACTED

def test_external_email_connector_unauthorized():
    connector = ExternalEmailConnector(api_key=None)
    assert not connector.is_authorized
    
    lead = Lead(lead_id="L-1", organisation="Test Org", problem="Needs automation", source="test", state="WAITING_FOR_HUMAN")
    success = connector.send_outreach(lead, "Test message", human_approval_id="dennis_approval_1")
    
    assert success is False
    assert lead.state == "WAITING_FOR_HUMAN"

def test_external_email_connector_authorized():
    connector = ExternalEmailConnector(api_key="fake-key-123")
    assert connector.is_authorized
    
    lead = Lead(lead_id="L-1", organisation="Test Org", problem="Needs automation", source="test", state="WAITING_FOR_HUMAN")
    success = connector.send_outreach(lead, "Test message", human_approval_id="dennis_approval_1")
    
    assert success is True
    assert lead.state == CONTACTED
    assert any("Sent via ExternalEmailConnector" in item.get("note", "") for item in lead.history)
