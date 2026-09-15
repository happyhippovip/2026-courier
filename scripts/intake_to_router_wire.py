#!/usr/bin/env python3
"""Minimal wiring from IdeaInbox -> CourierGoalPlanner -> OpportunityQueue."""

import hashlib
import json
import sys
import uuid
from pathlib import Path

# Ensure absolute imports work
SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.idea_inbox import IdeaInbox
from scripts.courier_goal_planner import CourierGoalPlanner
from scripts.opportunity_queue import Opportunity, OpportunityQueue
from scripts.next_safe_work_router import NextSafeWorkRouter

def process_one_idea(idea_text: str) -> None:
    # 1. Inject into IdeaInbox
    inbox = IdeaInbox()
    idea = inbox.add_idea(raw_text=idea_text)
    idea_id = idea["idea_id"]
    print(f"1. Injected Idea: {idea_id} -> '{idea_text}'")

    # 2. Plan next mission using CourierGoalPlanner
    planner = CourierGoalPlanner(max_write_missions=1, max_missions=5)
    decision = planner.plan_next_step(root_goal=idea_text, verified_history=[])
    
    if decision.decision != "CONTINUE" or not decision.next_mission:
        print(f"Planner blocked or satisfied: {decision.decision} - {decision.reason}")
        return

    mission = decision.next_mission
    print(f"2. Planner derived mission: {mission['mission_id']} for agent {mission.get('preferred_agent')}")

    # 3. Create Opportunity and add to queue
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    # Bypass exact dedupe for live test by appending a UUID to the hash base
    normalized_text = idea_text.strip().lower()
    unique_suffix = uuid.uuid4().hex[:8]
    dedupe_hash = hashlib.sha256(f"IDEA_{normalized_text}_{mission.get('action', 'discovery')}_{unique_suffix}".encode()).hexdigest()[:16]
    
    # Discovery mission from planner does not require write, so scope is safe local.
    opp = Opportunity(
        opportunity_id=mission["mission_id"],
        source="COURIER_GOAL_PLANNER",
        project="IDEA_INBOX_GOALS",
        description=mission.get("normalized_task", "Discovery"),
        objective_id=idea_id,
        priority=6,
        risk=mission.get("risk_class", "LOW"),
        estimated_cost=0.0,
        heavy_job=mission.get("is_heavy", False),
        status="READY",
        target_agent=mission.get("preferred_agent", "CLI1"),
        allowed_actions=[mission["task"]["action"]],
        allowed_scope=["SAFE_LOCAL_VALIDATION"] if not mission.get("requires_write") else ["UNKNOWN_WRITE"],
        dedupe_hash=dedupe_hash,
    )
    
    added = queue.add_opportunity(opp)
    if added:
        print(f"3. Enqueued Opportunity: {opp.opportunity_id}")
    else:
        print(f"3. Opportunity deduplicated (already exists): {opp.opportunity_id}")
    
    # Update IdeaInbox to mark as routed
    inbox.update_idea(idea_id, {"status": "ROUTED", "mission_id": mission["mission_id"]})

    # 4. Router visibility
    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
    res = router.evaluate_next_safe_work()
    recs = res.get("recommendations", {})
    
    target_worker = opp.target_agent
    worker_rec = recs.get(target_worker, {})
    
    print(f"4. Router visibility for {target_worker}:")
    print(json.dumps(worker_rec, indent=2))
    
    if worker_rec.get("task_id") == opp.opportunity_id:
        print("SUCCESS: Router recommended the new opportunity!")
    else:
        print("WARNING: Router did not recommend the new opportunity. It may have recommended another one, or blocked.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 intake_to_router_wire.py <goal_text>")
        sys.exit(1)
    process_one_idea(sys.argv[1])
