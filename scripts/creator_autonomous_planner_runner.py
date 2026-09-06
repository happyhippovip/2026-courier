#!/usr/bin/env python3
"""Creator Factory Autonomous Work Planner Runner.

Executes canonical asset discovery, ready-work queue building, work planning,
execution contract validation, review gate evaluation, and Chief return contract generation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.creator_asset_inventory import (
    CreatorAssetInventoryBuilder,
)
from scripts.creator_chief_contract import (
    ChiefResultStatus,
    CreatorChiefContractBuilder,
)
from scripts.creator_execution_contract import (
    CreatorExecutionContract,
)
from scripts.creator_review_gate import (
    CreatorReviewGate,
)
from scripts.creator_work_planner import (
    CreatorWorkPlanner,
    ExecutionClass,
    PlanStatus,
)
from scripts.creator_work_queue import (
    CreatorWorkQueueBuilder,
)


def run_creator_autonomous_planner(repo_dir: Path | None = None) -> dict:
    """Run full deterministic Creator Factory Work Planner pipeline."""
    base_dir = repo_dir or REPO_ROOT

    # 1. Discover canonical inventory
    builder = CreatorAssetInventoryBuilder(repo_dir=base_dir)
    inventory = builder.scan_content_directory()

    # 2. Build ready-work queue
    queue = CreatorWorkQueueBuilder.build_queue(inventory)

    # 3. Generate WorkPlans
    planner = CreatorWorkPlanner()
    plans = planner.plan_all(inventory, queue)

    # 4. Validate contracts, review gates, and Chief return payloads
    plan_dicts = []
    contract_evaluations = {}
    review_evaluations = {}
    chief_returns = {}

    for plan in plans:
        plan_dicts.append(plan.to_dict())

        # Execution Contract validation
        asset = inventory.assets.get(plan.content_id)
        current_state_hash = asset.asset_state_hash if asset else None
        contract_res = CreatorExecutionContract.validate_plan_for_execution(
            plan=plan,
            current_asset_state_hash=current_state_hash,
            repo_dir=base_dir,
        )
        contract_evaluations[plan.content_id] = contract_res.to_dict()

        # Review Gate evaluation
        review_res = CreatorReviewGate.evaluate_review_requirement(
            risk_class=plan.risk_class,
            publication_boundary=(plan.blocking_gate == "AUDIENCE_DECISION_GATE" or "UPLOAD" in plan.action_type),
        )
        review_evaluations[plan.content_id] = review_res.to_dict()

        # Chief Return Contract derivation
        if plan.status == PlanStatus.WAITING_HUMAN.value:
            chief_status = ChiefResultStatus.WAITING_FOR_USER.value
            useful_work = False
            rec_action = "AWAIT_HUMAN_AUDIENCE_DECISION"
        elif plan.status == PlanStatus.NO_USEFUL_NEW_WORK.value:
            chief_status = ChiefResultStatus.NO_USEFUL_NEW_WORK.value
            useful_work = False
            rec_action = "STANDBY_IDLE"
        elif plan.status == PlanStatus.READY_TO_EXECUTE.value:
            chief_status = ChiefResultStatus.DONE.value
            useful_work = True
            rec_action = f"DISPATCH_{plan.action_type}"
        else:
            chief_status = ChiefResultStatus.BLOCKED.value
            useful_work = False
            rec_action = "INVESTIGATE_BLOCKER"

        chief_contract = CreatorChiefContractBuilder.build_from_plan(
            plan=plan,
            result_status=chief_status,
            useful_work_completed=useful_work,
            review_decision=review_res.decision,
            recommended_next_action=rec_action,
        )
        chief_returns[plan.content_id] = chief_contract.to_dict()

    output_payload = {
        "schema_version": "1.0",
        "inventory_id": inventory.inventory_id,
        "queue_id": queue.queue_id,
        "plans": plan_dicts,
        "contract_evaluations": contract_evaluations,
        "review_evaluations": review_evaluations,
        "chief_returns": chief_returns,
    }

    # 5. Persist output manifest
    output_dir = base_dir / "events" / "ready-work"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "creator_work_plan.json"
    out_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    return output_payload


if __name__ == "__main__":
    res = run_creator_autonomous_planner()
    print("=== CREATOR FACTORY AUTONOMOUS WORK PLANS GENERATED ===")
    print(f"Total Plans: {len(res['plans'])}")
    for p in res["plans"]:
        cid = p["content_id"]
        action = p["action_type"]
        status = p["status"]
        chief_st = res["chief_returns"][cid]["result_status"]
        rev_dec = res["review_evaluations"][cid]["decision"]
        print(f" - [{cid}]: action={action}, plan_status={status}, chief_status={chief_st}, review={rev_dec}")
