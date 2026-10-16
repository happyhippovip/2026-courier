#!/usr/bin/env python3
"""Read-only gate for the Courier Motor workflow.

Answers one question without starting the server or installing anything:
would GITHUB-DISPATCHER be able to claim a task from the committed state?
It mirrors the claim conditions in server/app.py (claim_task). A step that
sets requires_independent_review is additionally refused until a different
actor accepts it. main() does not write the state file. server/app.py itself
is unchanged and does not yet apply that review rule.
Standard library only, so an idle run needs no pip install.
"""
import json
import os
import sys

STATE_FILE = os.environ.get("COURIER_STATE_FILE", "server/state/central_state.json")
DISPATCHER_ID = "GITHUB-DISPATCHER"
_REVIEW_SOURCES = frozenset({"PYTEST", "LEDGER_RECEIPT", "CI"})


def record_independent_review(step, review) -> bool:
    """Store one review on the step. A repeated event_id is not applied again."""
    if not isinstance(step, dict) or not isinstance(review, dict):
        return False
    event_id = review.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        return False
    bucket = step.setdefault("independent_reviews", [])
    if not isinstance(bucket, list):
        return False
    if any(isinstance(item, dict) and item.get("event_id") == event_id for item in bucket):
        return False
    bucket.append({
        "event_id": event_id,
        "reviewer_id": review.get("reviewer_id"),
        "author_id": review.get("author_id", step.get("author_id")),
        "source": review.get("source"),
        "evidence_ref": review.get("evidence_ref"),
        "verdict": review.get("verdict"),
    })
    return True


def independent_review_ok(step) -> bool:
    """True when this step does not demand a review, or the latest review is independent.

    A self-report, the producing actor, a missing evidence pointer, or a
    non-ACCEPT verdict does not open the gate.
    """
    if not isinstance(step, dict) or not step.get("requires_independent_review"):
        return True
    reviews = step.get("independent_reviews")
    if not isinstance(reviews, list):
        single = step.get("independent_review")
        reviews = [single] if isinstance(single, dict) else []
    if not reviews or not isinstance(reviews[-1], dict):
        return False
    latest = reviews[-1]
    author = latest.get("author_id") or step.get("author_id")
    reviewer = latest.get("reviewer_id")
    if not isinstance(author, str) or not author or not isinstance(reviewer, str) or not reviewer:
        return False
    if reviewer == author:
        return False
    if latest.get("source") not in _REVIEW_SOURCES:
        return False
    evidence = latest.get("evidence_ref")
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    return latest.get("verdict") == "ACCEPT"


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
            if not independent_review_ok(step):
                continue
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
