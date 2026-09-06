#!/usr/bin/env python3
"""Mission 193: Continuous Local Flow & Next-Work Selector Contract.

Evaluates queue and gate states deterministically when tasks complete:
- Selects NEXT_TASK_AVAILABLE if a verified safe task exists
- Emits WAITING_HUMAN if a human audience/spend gate is required
- Emits SAFE_IDLE if no actionable work exists (rejects filler tasks)
- 100% deterministic, 0 model spend
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from opportunity_queue import Opportunity, OpportunityQueue
    from queue_hygiene_manager import QueueHygieneManager
except ImportError:
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.queue_hygiene_manager import QueueHygieneManager


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class FlowDecision(str, Enum):
    NEXT_TASK_AVAILABLE = "NEXT_TASK_AVAILABLE"
    SAFE_IDLE = "SAFE_IDLE"
    WAITING_HUMAN = "WAITING_HUMAN"
    PERMISSION_BLOCK = "PERMISSION_BLOCK"
    HIGH_RISK_REVIEW = "HIGH_RISK_REVIEW"


@dataclass
class NextWorkResult:
    decision: FlowDecision
    opportunity_id: Optional[str] = None
    opportunity: Optional[Dict[str, Any]] = None
    reason: str = ""
    active_scopes: List[str] = field(default_factory=list)
    spend_eur: float = 0.0
    model_calls: int = 0
    decided_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d


class ContinuousLocalFlowController:
    """Deterministic contract evaluator selecting next safe work without human WEITER."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.queue_manager = QueueHygieneManager(repo_dir=self.repo_dir)

    def evaluate_next_work(
        self,
        active_mutation_scopes: Optional[Set[str]] = None,
        heavy_job_running: bool = False,
    ) -> NextWorkResult:
        """Determines the next autonomous action for Computer A."""
        active_scopes = set(active_mutation_scopes or [])
        q = OpportunityQueue(repo_dir=self.repo_dir)
        all_opps = q.list_opportunities()

        # 1. Partition opportunities
        ready_tasks = [o for o in all_opps if o.status == "READY"]
        human_gates = [o for o in all_opps if o.status in ("WAITING_FOR_HUMAN", "HUMAN_GATE")]
        money_gates = [o for o in all_opps if o.status == "PAYMENT_APPROVAL_REQUIRED"]
        blocked_tasks = [o for o in all_opps if o.status == "BLOCKED"]

        # 2. Evaluate Ready Tasks by Priority Descending
        sorted_ready = sorted(ready_tasks, key=lambda x: x.priority, reverse=True)

        for candidate in sorted_ready:
            # Check historical deduplication
            if self.queue_manager.is_task_completed_in_history(candidate.opportunity_id):
                continue

            # Check heavy job constraints
            if heavy_job_running and candidate.heavy_job:
                continue

            # Check scope exclusivity
            cand_scopes = set(candidate.allowed_scope or [candidate.project or "GLOBAL"])
            if any(s in active_scopes for s in cand_scopes):
                continue

            # Check high risk boundary
            if candidate.risk == "HIGH" or "security" in candidate.description.lower():
                return NextWorkResult(
                    decision=FlowDecision.HIGH_RISK_REVIEW,
                    opportunity_id=candidate.opportunity_id,
                    opportunity=candidate.to_dict(),
                    reason="Task classified as HIGH_RISK requires Chief/reviewer gate",
                    active_scopes=list(active_scopes),
                )

            # Safe next task found!
            return NextWorkResult(
                decision=FlowDecision.NEXT_TASK_AVAILABLE,
                opportunity_id=candidate.opportunity_id,
                opportunity=candidate.to_dict(),
                reason=f"Candidate {candidate.opportunity_id} is safe, ready, and scope-disjoint",
                active_scopes=list(active_scopes),
            )

        # 3. If no ready task, check if blocked exclusively by Human Gates
        if human_gates or money_gates:
            target_gate = (human_gates or money_gates)[0]
            return NextWorkResult(
                decision=FlowDecision.WAITING_HUMAN,
                opportunity_id=target_gate.opportunity_id,
                opportunity=target_gate.to_dict(),
                reason="All remaining pending work requires explicit human legal/spend authorization",
                active_scopes=list(active_scopes),
            )

        # 4. Clean, legitimate idle state (Zero busywork / zero manufactured filler)
        return NextWorkResult(
            decision=FlowDecision.SAFE_IDLE,
            opportunity_id=None,
            opportunity=None,
            reason="No actionable backlog items pending. Safe quiescent idle state.",
            active_scopes=list(active_scopes),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuous Local Flow Controller (Mission 193)")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate next safe work candidate")
    args = parser.parse_args()

    controller = ContinuousLocalFlowController()
    res = controller.evaluate_next_work()
    print(json.dumps(res.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
