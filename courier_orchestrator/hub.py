"""Courier Hub + Hubwriter. The Hubwriter is the only writer (SINGLE_WRITER)."""
from __future__ import annotations

import json
from pathlib import Path

from .models import (HUMAN_GATES, Delta, Goal, GoalStatus, Result, Task, TaskStatus,
                     Verification, WorkerContract, to_dict)


class HubwriterRejected(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class Hubwriter:
    """Many eyes, one pen. Writes a delta only for an independently verified result."""

    WRITER_ID = "hubwriter"

    def __init__(self, journal_path: Path | None = None):
        self.deltas: list[Delta] = []
        self.journal_path = journal_path

    def accept(self, contract: WorkerContract, result: Result, verification: Verification | None) -> Delta:
        if verification is None:
            raise HubwriterRejected("RESULT_RECEIVED_NOT_VERIFIED")
        if verification.verifier_id in (result.worker_id, self.WRITER_ID):
            raise HubwriterRejected("SELF_PASS_NOT_ACCEPTANCE")
        if (verification.task_id, verification.attempt) != (result.task_id, result.attempt):
            raise HubwriterRejected("VERIFICATION_MISMATCH")
        if verification.verdict != "PASS":
            raise HubwriterRejected("NOT_VERIFIED")
        if not set(result.requested_scope) <= set(contract.allowed_scope):
            raise HubwriterRejected("SCOPE_ESCALATION")
        delta = Delta(len(self.deltas) + 1, result.goal_id, result.task_id, self.WRITER_ID,
                      verification.verifier_id, {"output": result.output, "evidence": list(result.evidence),
                                                 "cost_eur": result.cost_eur})
        self.deltas.append(delta)
        if self.journal_path:
            with open(self.journal_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(to_dict(delta), sort_keys=True) + "\n")
        return delta


def gate_hits(task: Task, goal: Goal) -> list[str]:
    hits = []
    for a in task.actions:
        gate = a if a in HUMAN_GATES else "unknown_external_effect"
        if gate not in goal.authorization:
            hits.append(gate)
    return hits


def contract_for(task: Task, role: str) -> WorkerContract:
    return WorkerContract(task.task_id, task.goal_id, role, ("brain:goal", f"task:{task.task_id}"),
                          tuple(task.scope), ("deploy", "force_push", "delete", "edit:server/app.py",
                                              "edit:.github/workflows", "self_grant_scope"),
                          task.expected_output, tuple(task.acceptance_criteria), task.cost_limit_eur)


def board(goal: Goal, tasks: list[Task], governor, deltas) -> dict:
    """Goal-level Grokboard card."""
    st = lambda *s: [t.task_id for t in tasks if t.status in s]
    nxt = next((t.task_id for t in tasks if t.status == TaskStatus.QUEUED), None)
    needs = st(TaskStatus.NEEDS_HUMAN)
    return {"goal_id": goal.goal_id, "status": goal.status.value,
            "budget": {"eur": goal.budget_eur, "spent": goal.spent_eur, "remaining": governor.remaining},
            "workers": sorted({t.assigned_worker for t in tasks if t.assigned_worker}),
            "running": st(TaskStatus.RUNNING), "waiting": st(TaskStatus.QUEUED) + needs,
            "verified_results": len(deltas),
            "next_action": ("HUMAN: " + needs[0]) if needs else (nxt or "none"),
            "VERIFIED_USEFUL_RESULTS_PER_REAL_EURO": governor.metric()}
