import time
import json
from datetime import datetime, timezone
from pathlib import Path
from scripts.opportunity_os.opportunity_record import OpportunityRecord, OpportunityDomain, UnitEconomics
from scripts.opportunity_os.evidence_hierarchy import EvidenceItem, EvidenceLevel
from scripts.opportunity_os.orchestrator import OpportunityOsOrchestrator

def main():
    print("🧠 KÜNSTLICHES GEHIRN (CHIEF & WORKER SYNC) - DAEMON STARTED")
    print("Monitoring and running Opportunity OS in continuous loop...")
    
    orchestrator = OpportunityOsOrchestrator()
    
    opp1 = OpportunityRecord(
        opportunity_id="OPP-DAEMON-TEST-01",
        title="Automated Security Audits for Multi-Agent Systems",
        domain=OpportunityDomain.B2B_AUTOMATION,
        problem="Agent recursion loops and lock contention",
        customer="Senior AI Engineers",
        evidence_sources=[
            EvidenceItem(
                evidence_id="EVID-01",
                level=EvidenceLevel.LEVEL_B, 
                source_name="Email/Inbox",
                description="Verified Market Demand from CP-01 via Email",
                verified=True,
                raw_reference="inbox://P-01"
            )
        ],
        expected_cost_eur=0.0,
        expected_revenue_eur=99.0,
        legal_risk=0.1,
        fraud_risk=0.0,
        next_safe_test="Simulate delivery workflow",
        unit_economics=UnitEconomics(selling_price_eur=99.0, cost_of_delivery_eur=0.0)
    )
    
    opp2 = OpportunityRecord(
        opportunity_id="OPP-DAEMON-TEST-02",
        title="Market Defense Strategy Generation",
        domain=OpportunityDomain.FINANCIAL_RESEARCH,
        problem="Inefficient hedging against tail risk",
        customer="Retail Quant Traders",
        evidence_sources=[
            EvidenceItem(
                evidence_id="EVID-02",
                level=EvidenceLevel.LEVEL_A,
                source_name="HackerNews",
                description="HackerNews Discussion on Market Defense",
                verified=True,
                raw_reference="https://hn.example.com"
            )
        ],
        expected_cost_eur=0.0,
        expected_revenue_eur=499.0,
        legal_risk=0.1,
        fraud_risk=0.0,
        next_safe_test="Backtest rules against historical data",
        unit_economics=UnitEconomics(selling_price_eur=499.0, cost_of_delivery_eur=0.0)
    )

    orchestrator.ingest_opportunity(opp1)
    orchestrator.ingest_opportunity(opp2)
    
    # Run 3 cycles
    for i in range(3):
        print(f"\n--- Cycle {i+1} at {datetime.now(timezone.utc).isoformat()} ---")
        result = orchestrator.run_autonomous_cycle()
        print(json.dumps(result.__dict__, indent=2))
        time.sleep(2)
        
    print("\n✅ Daemon run completed successfully. (Limited to 3 iterations for Github Sync)")

if __name__ == "__main__":
    main()
