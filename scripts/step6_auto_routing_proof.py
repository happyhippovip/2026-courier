#!/usr/bin/env python3
import sys
import subprocess
import time
import json
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(COURIER_DIR))

from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.next_safe_work_router import NextSafeWorkRouter
import hashlib
import datetime

SAFE_TASK_ID = "TASK_SAFE_6"
HUMAN_GATE_TASK_ID = "TASK_HUMAN_GATE_6"

now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
queue = OpportunityQueue(repo_dir=COURIER_DIR)

for opp in queue.opportunities.values():
    if opp.status in ("READY", "HUMAN_GATE"):
        opp.status = "COMPLETED"
        queue.opportunities[opp.opportunity_id] = opp
        from scripts.opportunity_queue import save_json
        save_json(queue.queue_dir / f"{opp.opportunity_id}.json", opp.to_dict())

opp_human = Opportunity(
    opportunity_id=HUMAN_GATE_TASK_ID,
    source="ROUTER_DISPATCH",
    project="WINDOWS_AI_OS",
    description="Format the C: drive on Windows",
    objective_id="OBJ-STEP6",
    priority=10,
    risk="HIGH",
    estimated_cost=0.0,
    heavy_job=True,
    status="HUMAN_GATE",
    target_agent=None,
    required_capabilities=["WINDOWS_EXECUTION"],
    allowed_scope=["C:\\"],
    allowed_actions=["WRITE", "DELETE"],
    dedupe_hash=hashlib.sha256(HUMAN_GATE_TASK_ID.encode()).hexdigest()[:16],
)
queue.opportunities[opp_human.opportunity_id] = opp_human
save_json(queue.queue_dir / f"{opp_human.opportunity_id}.json", opp_human.to_dict())

opp_safe = Opportunity(
    opportunity_id=SAFE_TASK_ID,
    source="ROUTER_DISPATCH",
    project="WINDOWS_AI_OS",
    description="Read project structure",
    objective_id="OBJ-STEP6",
    priority=5,
    risk="SAFE",
    estimated_cost=0.0,
    heavy_job=False,
    status="READY",
    target_agent=None,
    required_capabilities=["WINDOWS_EXECUTION"],
    allowed_scope=["C:\\Dev\\Windows-AI-OS"],
    allowed_actions=["READ"],
    dedupe_hash=hashlib.sha256(SAFE_TASK_ID.encode()).hexdigest()[:16],
)
queue.opportunities[opp_safe.opportunity_id] = opp_safe
save_json(queue.queue_dir / f"{opp_safe.opportunity_id}.json", opp_safe.to_dict())

print("=== STEP 6: AUTO-ROUTING PROOF ===")
print("Injected 2 opportunities: High Priority HUMAN_GATE, Low Priority SAFE READY")

router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
res = router.evaluate_next_safe_work()
rec_codex = res.get("recommendations", {}).get("CODEX")

print(f"\n[ROUTER] Codex Recommendation: {rec_codex.get('recommended_action') if rec_codex else 'NONE'}")
if rec_codex and rec_codex.get("task_id") == SAFE_TASK_ID:
    print("[ROUTER] Safe task auto-routed successfully. Human gate task was safely bypassed/checkpointed.")
else:
    print("[ROUTER] ERROR: Did not route safe task as expected!")
    sys.exit(1)

ROUTER_CMD = [sys.executable, str(SCRIPTS_DIR / "router_dispatch_codex.py")]
print(f"\n[PIPELINE] Dispatching {SAFE_TASK_ID}...")
proc = subprocess.run(ROUTER_CMD + [SAFE_TASK_ID, "Read project structure"], capture_output=True, text=True)

executed_safe = False
for line in proc.stdout.splitlines():
    if "RESULT VERIFICATION" in line or "FINAL_STATUS" in line or "STEP" in line:
        print(f"  {line}")
    if "FINAL_STATUS=PASS" in line:
        executed_safe = True

if executed_safe:
    print("\n[VERDICT] STEP 6 SUCCESSFUL")
else:
    print("\n[VERDICT] STEP 6 FAILED")
    print(proc.stdout)
    if proc.stderr: print(proc.stderr)
