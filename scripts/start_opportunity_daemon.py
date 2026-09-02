import time
import json
import glob
from datetime import datetime, timezone
from pathlib import Path
from scripts.opportunity_os.opportunity_record import OpportunityRecord, OpportunityDomain, UnitEconomics
from scripts.opportunity_os.evidence_hierarchy import EvidenceItem, EvidenceLevel
from scripts.opportunity_os.orchestrator import OpportunityOsOrchestrator

def load_live_opportunities():
    opps = []
    # Search for all market experiments
    files = glob.glob("events/revenue-opportunities/market_intelligence/MARKET_EXPERIMENT_*.json")
    for f_path in files:
        with open(f_path, 'r') as f:
            data = json.load(f)
            
            # Map pricing to domain logic
            price = data.get("price_eur", 0.0)
            target = data.get("target_offering", "")
            
            domain = OpportunityDomain.SOFTWARE
            if "AUDIT" in target:
                domain = OpportunityDomain.B2B_AUTOMATION
            elif "KIBEY" in target:
                domain = OpportunityDomain.SOFTWARE
                
            # Create a real evidence item from the file
            evidence = EvidenceItem(
                evidence_id=f"EVID-{data['experiment_id']}",
                level=EvidenceLevel.LEVEL_B if data.get("evidence_class") == "SOURCE_SUPPORTED_PAIN_PATTERN" else EvidenceLevel.LEVEL_C,
                source_name=data.get("public_source", "Unknown"),
                description=data.get("observed_pain", "Unknown"),
                verified=True,
                raw_reference=data.get("source_date", "")
            )
            
            opp = OpportunityRecord(
                opportunity_id=data["experiment_id"],
                title=data.get("message_body", {}).get("subject", target),
                domain=domain,
                problem=data.get("observed_pain", "Unknown"),
                customer=data.get("buyer_role", "Unknown"),
                evidence_sources=[evidence],
                expected_cost_eur=0.0,
                expected_revenue_eur=price,
                legal_risk=0.1,
                fraud_risk=0.0,
                next_safe_test="Monitor inbound response and convert",
                unit_economics=UnitEconomics(selling_price_eur=price, cost_of_delivery_eur=0.0)
            )
            opps.append(opp)
    return opps

def main():
    print("🧠 KÜNSTLICHES GEHIRN - LIVE MARKET DAEMON STARTED")
    
    orchestrator = OpportunityOsOrchestrator()
    live_opps = load_live_opportunities()
    
    if not live_opps:
        print("No live opportunities found.")
        return
        
    print(f"Loaded {len(live_opps)} live market experiments into the OS.")
    for opp in live_opps:
        orchestrator.ingest_opportunity(opp)
    
    print("\nExecuting Autonomous Cycle on LIVE data...")
    result = orchestrator.run_autonomous_cycle()
    print("\n--- CYCLE OUTCOME ---")
    print(json.dumps(result.__dict__, indent=2))
    
    print("\n✅ Live Daemon cycle completed.")

if __name__ == "__main__":
    main()
