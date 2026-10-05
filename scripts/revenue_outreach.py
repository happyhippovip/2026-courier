import sys
from pathlib import Path
from courier_runtime.revenue import Lead, CONTACTED, HUMAN_GATED

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

class ExternalEmailConnector:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.is_authorized = bool(api_key)

    def send_outreach(self, lead: Lead, message: str, human_approval_id: str):
        if not self.is_authorized:
            print(f"WARN: External connectors not authorized. Cannot send to {lead.organisation}.")
            return False
            
        print(f"Sending outreach to {lead.organisation} via external connector...")
        print(f"Message: {message}")
        
        # In a real scenario, API calls go here.
        
        # Transition lead to CONTACTED
        lead.move(CONTACTED, at=1000, human_approval=human_approval_id, note="Sent via ExternalEmailConnector")
        return True

def run_outreach():
    print("Starting Revenue Outreach Sequence...")
    # Setup dummy lead that was approved
    lead = Lead(lead_id="L-1", organisation="Test Org", problem="Needs automation", source="test", state="WAITING_FOR_HUMAN")
    
    connector = ExternalEmailConnector(api_key=None) # Awaiting real credentials
    
    approval_id = "dennis_approval_rv08"
    success = connector.send_outreach(lead, "Hello, we can help with automation.", human_approval_id=approval_id)
    
    if not success:
        print("Outreach blocked: Missing external API credentials.")
        
if __name__ == "__main__":
    run_outreach()
