"""Command-line interface for Courier Symphony Arbitrage Research Engine.

Allows offline replay and deterministic dry-run audits without any real trading or wallet signing.
Safety Invariants:
- REAL_TRADES=0
- WALLET_SIGNING=NO
- ADDITIONAL_SPEND=0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from courier_core.arbi.models import NormalizedPair
from courier_core.arbi.service import ArbitrageResearchPipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Symphony Arbitrage Research CLI")
    parser.add_argument("--capital", type=float, default=100.0, help="Virtual paper-trading capital (USD)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Run audit without writing to disk")
    args = parser.parse_args(argv)

    pipeline = ArbitrageResearchPipeline(
        virtual_capital_usd=args.capital, persist=not args.dry_run
    )
    
    # Run cycle
    snapshot = pipeline.run_cycle()

    if args.json:
        sys.stdout.write(json.dumps(snapshot, indent=2) + "\n")
    else:
        sys.stdout.write(f"=== {snapshot['title']} ===\n")
        sys.stdout.write(f"Timestamp: {snapshot['at']}\n")
        sys.stdout.write("Pairs Monitored:\n")
        for p in snapshot["pairs_monitored"]:
            sys.stdout.write(f"  - {p['pair']}: venues={p['venues']}, spread={p['spread_bps']} bps, status={p['status']}\n")
        sim = snapshot["simulation"]
        sys.stdout.write(f"Simulated Net Profit: +{sim['net_simulated_profit_eur']} EUR (ROI: +{sim['net_roi_pct']}%)\n")
        sys.stdout.write(f"Simulated Loss: -{sim['simulated_loss_eur']} EUR\n")
        sys.stdout.write(f"Success Rate: {sim['success_rate_pct']}%\n")
        sys.stdout.write(f"Best Strategy: {sim['best_simulated_strategy']}\n")
        sys.stdout.write(f"Verified Actual Revenue: {snapshot['verified_actual_revenue']['amount_eur']} EUR (Status: {snapshot['verified_actual_revenue']['status']})\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
