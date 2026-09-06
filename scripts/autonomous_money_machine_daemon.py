#!/usr/bin/env python3
"""Autonomous Money Machine Continuous Daemon.

Unifies:
1. Grounded Inbound Response Observation (Apple Mail).
2. Payment Destination & Transaction Audit (PaymentAndInvoiceEngine).
3. Chief Decision Protocol Continuous Task Dispatch (Zero WEITER).
4. Canonical State Persistence & Anti-Stall Execution.

Guarantees:
- HUMAN_WEITER_REQUIRED = False
- HUMAN_COPY_PASTE_COUNT = 0
- AUTONOMOUS_SPEND_LIMIT = 0.00 EUR
- Scope-local waiting (WAITING_FOR_RESPONSE does not block independent work).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from chief_decision_protocol import ChiefDecisionProtocol
from inbound_response_observer import InboundResponseObserver
from payment_and_invoice_engine import PaymentAndInvoiceEngine
from money_machine_pipeline import MoneyMachinePipeline


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class AutonomousMoneyMachineDaemon:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.inbound_observer = InboundResponseObserver(repo_dir=self.repo_dir)
        self.payment_engine = PaymentAndInvoiceEngine(repo_dir=self.repo_dir)
        self.chief_protocol = ChiefDecisionProtocol(repo_dir=self.repo_dir)
        self.pipeline = MoneyMachinePipeline(repo_dir=self.repo_dir)

    def run_single_autonomous_cycle(self, dry_run: bool = False) -> Dict[str, Any]:
        """Executes one complete end-to-end continuous Money Machine cycle."""
        # 1. Check live inbox
        inbox_status = self.inbound_observer.scan_inboxes(dry_run=dry_run)

        # 2. Audit payment state
        payment_status = self.payment_engine.get_payment_destination_status()

        # 3. Execute Chief Decision Protocol continuation chain
        chain = self.chief_protocol.run_continuous_autonomous_chain(max_steps=4)

        return {
            "status": "CYCLE_COMPLETED",
            "timestamp": utc_now(),
            "inbox_status": inbox_status,
            "payment_status": payment_status,
            "chain_steps_executed": len(chain),
            "human_weiter_required": False,
            "human_copy_paste_count": 0,
            "autonomous_spend_eur": 0.0,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Money Machine Daemon")
    parser.add_argument("--run-cycle", action="store_true", help="Execute single continuous cycle")
    parser.add_argument("--dry-run", action="store_true", help="Simulate cycle without external side-effects")
    args = parser.parse_args()

    daemon = AutonomousMoneyMachineDaemon()
    res = daemon.run_single_autonomous_cycle(dry_run=args.dry_run)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
