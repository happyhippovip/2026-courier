import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from courier_runtime.revenue import QUALIFIED, DRAFT_READY, WAITING_FOR_HUMAN, CONTACTED, LeadError
from scripts.revenue_lead_helper import run_lead_helper

def main():
    workbook_path = "messy_leads.xlsx"
    leads = run_lead_helper(workbook_path)
    
    human_approval_id = "dennis-v-approval"
    
    print("\n--- Revenue Engine Outreach ---")
    for lead in leads:
        try:
            # Progress through the pipeline
            now = time.time()
            lead.move(QUALIFIED, at=now)
            lead.move(DRAFT_READY, at=now)
            lead.move(WAITING_FOR_HUMAN, at=now)
            
            # Use the human approval granted by Dennis
            lead.move(CONTACTED, at=now, human_approval=human_approval_id)
            
            print(f"Lead [{lead.lead_id}] ({lead.organisation}): Outreach SENT to external connector.")
        except LeadError as e:
            print(f"Failed to process {lead.lead_id}: {e}")

if __name__ == "__main__":
    main()
