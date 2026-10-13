"""Data models: Goal, Task, WorkerContract, Result, Verification, Delta."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum

HUMAN_GATES = frozenset({
    "payment", "purchase", "subscription", "oauth", "publication",
    "destructive", "legal_commitment", "scope_escalation", "unknown_external_effect",
})


class GoalStatus(str, Enum):
    WORKING = "WORKING"
    NEEDS_YOU = "NEEDS_YOU"
    DONE = "DONE"
    FAILED = "FAILED"


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RESULT_RECEIVED = "RESULT_RECEIVED"
    VERIFIED = "VERIFIED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_HUMAN = "NEEDS_HUMAN"


@dataclass
class Goal:
    goal_id: str
    project_id: str
    title: str
    budget_eur: float
    deadline: str
    authorization: tuple = ()          # human gates the human pre-approved
    status: GoalStatus = GoalStatus.WORKING
    spent_eur: float = 0.0


@dataclass(frozen=True)
class WorkerContract:
    task_id: str
    goal_id: str
    worker_role: str
    required_context: tuple
    allowed_scope: tuple
    forbidden_actions: tuple
    expected_output: str
    acceptance_criteria: tuple
    cost_limit_eur: float


@dataclass
class Task:
    task_id: str
    goal_id: str
    capability: str
    scope: tuple
    expected_output: str
    acceptance_criteria: tuple
    cost_limit_eur: float
    actions: tuple = ()                # declared side effects (checked vs gates)
    depends_on: tuple = ()
    status: TaskStatus = TaskStatus.QUEUED
    attempts: int = 0
    assigned_worker: str | None = None


@dataclass(frozen=True)
class Result:
    task_id: str
    goal_id: str
    attempt: int
    worker_id: str
    output: dict
    requested_scope: tuple
    cost_eur: float
    evidence: tuple = ()
    self_verdict: str | None = None    # a worker's own PASS is informative only


@dataclass(frozen=True)
class Verification:
    task_id: str
    attempt: int
    verifier_id: str
    verdict: str                        # PASS | FAIL
    reasons: tuple = ()
    cost_eur: float = 0.0


@dataclass(frozen=True)
class Delta:
    seq: int
    goal_id: str
    task_id: str
    writer: str
    verifier_id: str
    payload: dict


def to_dict(obj) -> dict:
    d = asdict(obj)
    return {k: (v.value if isinstance(v, Enum) else v) for k, v in d.items()}
