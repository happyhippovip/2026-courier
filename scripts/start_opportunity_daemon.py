#!/usr/bin/env python3
"""Opportunity OS Live Market Daemon.

Loads market experiment intelligence from events/revenue-opportunities/market_intelligence
and triggers autonomous opportunity evaluation.
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

# Optional Opportunity OS imports
try:
    from scripts.opportunity_os.opportunity_record import OpportunityRecord, OpportunityDomain, UnitEconomics
    from scripts.opportunity_os.evidence_hierarchy import EvidenceItem, EvidenceLevel
    from scripts.opportunity_os.orchestrator import OpportunityOsOrchestrator
    OPPORTUNITY_OS_AVAILABLE = True
except ImportError:
    OPPORTUNITY_OS_AVAILABLE = False
    OpportunityRecord = None
    OpportunityDomain = None
    UnitEconomics = None
    EvidenceItem = None
    EvidenceLevel = None
    OpportunityOsOrchestrator = None


def load_live_opportunities(repo_dir: str | Path | None = None) -> list:
    if repo_dir is None:
        repo_dir = Path(__file__).resolve().parent.parent
    else:
        repo_dir = Path(repo_dir).resolve()

    opps = []
    search_pattern = str(repo_dir / "events" / "revenue-opportunities" / "market_intelligence" / "MARKET_EXPERIMENT_*.json")
    files = sorted(glob.glob(search_pattern))
    for f_path in files:
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            price = data.get("price_eur", 0.0)
            target = data.get("target_offering", "")

            if OPPORTUNITY_OS_AVAILABLE and OpportunityDomain is not None:
                domain = OpportunityDomain.SOFTWARE
                if "AUDIT" in target:
                    domain = OpportunityDomain.B2B_AUTOMATION
                elif "KIBEY" in target:
                    domain = OpportunityDomain.SOFTWARE

                evidence = EvidenceItem(
                    evidence_id=f"EVID-{data['experiment_id']}",
                    level=EvidenceLevel.LEVEL_B if data.get("evidence_class") == "SOURCE_SUPPORTED_PAIN_PATTERN" else EvidenceLevel.LEVEL_C,
                    source_name=data.get("public_source", "Unknown"),
                    description=data.get("observed_pain", "Unknown"),
                    verified=True,
                    raw_reference=data.get("source_date", ""),
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
                    unit_economics=UnitEconomics(selling_price_eur=price, cost_of_delivery_eur=0.0),
                )
            else:
                domain_str = "B2B_AUTOMATION" if "AUDIT" in target else "SOFTWARE"
                evidence = {
                    "evidence_id": f"EVID-{data.get('experiment_id')}",
                    "level": "LEVEL_B" if data.get("evidence_class") == "SOURCE_SUPPORTED_PAIN_PATTERN" else "LEVEL_C",
                    "source_name": data.get("public_source", "Unknown"),
                    "description": data.get("observed_pain", "Unknown"),
                    "verified": True,
                    "raw_reference": data.get("source_date", ""),
                }
                opp = {
                    "opportunity_id": data.get("experiment_id"),
                    "title": data.get("message_body", {}).get("subject", target),
                    "domain": domain_str,
                    "problem": data.get("observed_pain", "Unknown"),
                    "customer": data.get("buyer_role", "Unknown"),
                    "evidence_sources": [evidence],
                    "expected_cost_eur": 0.0,
                    "expected_revenue_eur": price,
                    "legal_risk": 0.1,
                    "fraud_risk": 0.0,
                    "next_safe_test": "Monitor inbound response and convert",
                    "unit_economics": {"selling_price_eur": price, "cost_of_delivery_eur": 0.0},
                }

            opps.append(opp)
        except Exception as e:
            print(f"Warning: Failed to load experiment {f_path}: {e}", file=sys.stderr)

    return opps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Opportunity OS Live Market Daemon")
    parser.add_argument("--repo-dir", help="Path to repository root")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON status")
    args = parser.parse_args(argv)

    if not args.json:
        print("🧠 KÜNSTLICHES GEHIRN - LIVE MARKET DAEMON STARTED")

    live_opps = load_live_opportunities(repo_dir=args.repo_dir)

    if not live_opps:
        if args.json:
            print(json.dumps({"status": "NO_OPPORTUNITIES_FOUND", "loaded_count": 0}))
        else:
            print("No live opportunities found.")
        return 0

    if not OPPORTUNITY_OS_AVAILABLE:
        if args.json:
            print(json.dumps({
                "status": "DEPENDENCY_UNAVAILABLE",
                "reason": "scripts.opportunity_os not installed in this environment",
                "loaded_experiments_count": len(live_opps)
            }, indent=2))
        else:
            print(f"Warning: scripts.opportunity_os not found. Loaded {len(live_opps)} raw experiments.")
        return 0

    if not args.json:
        print(f"Loaded {len(live_opps)} live market experiments into the OS.")
    orchestrator = OpportunityOsOrchestrator()
    for opp in live_opps:
        orchestrator.ingest_opportunity(opp)

    if not args.json:
        print("\nExecuting Autonomous Cycle on LIVE data...")
    result = orchestrator.run_autonomous_cycle()

    if args.json:
        print(json.dumps(result.__dict__, indent=2, default=str))
    else:
        print("\n--- CYCLE OUTCOME ---")
        print(json.dumps(result.__dict__, indent=2, default=str))
        print("\n✅ Live Daemon cycle completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
