#!/usr/bin/env python3
"""Read-only gate for the Courier Motor workflow.

Answers one question without starting the server or installing anything:
would GITHUB-DISPATCHER be able to claim a task from the committed state?
It mirrors the claim conditions in server/app.py (claim_task) and never
writes state, so ledger/DurableResult semantics are untouched.
Standard library only, so an idle run needs no pip install.
"""
import json
import os
import sys

STATE_FILE = os.environ.get("COURIER_STATE_FILE", "server/state/central_state.json")
DISPATCHER_ID = "GITHUB-DISPATCHER"


def has_dispatchable_work(state):
    worker = state.get("workers", {}).get(DISPATCHER_ID, {})
    if worker.get("current_task"):
        return False  # claim_task would answer WORKER_BUSY
    for goal in state.get("goals", {}).values():
        if goal.get("status") != "ACTIVE" or "workflow_plan" not in goal:
            continue
        idx = goal.get("current_step_index", 0)
        if idx >= len(goal["workflow_plan"]):
            continue
        step = goal["workflow_plan"][idx]
        if step.get("status") == "QUEUED" and "github" in step.get("target_agent", "linux").lower():
            return True
    return False


def main():
    if not os.path.exists(STATE_FILE):
        state = {}
    else:
        with open(STATE_FILE) as f:
            state = json.load(f)
    work = has_dispatchable_work(state)
    print(f"[Motor precheck] {STATE_FILE}: {'pending GitHub work' if work else 'idle'}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as f:
            f.write(f"has_work={'true' if work else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
