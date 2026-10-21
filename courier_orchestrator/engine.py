"""Event-driven loop: each accepted delta triggers the next task (no polling)."""
from __future__ import annotations

from .hub import Hubwriter, HubwriterRejected, board, contract_for, gate_hits
from .models import Goal, GoalStatus, Task, TaskStatus
from .router import CostGovernor, NoWorker, route
from .workers import MockPruefer, MockWorker

MAX_ATTEMPTS = 2


class Orchestrator:
    def __init__(self, goal: Goal, tasks: list[Task], workers: dict[str, MockWorker],
                 verifier: MockPruefer, hubwriter: Hubwriter | None = None):
        self.goal, self.tasks, self.workers, self.verifier = goal, tasks, workers, verifier
        self.hub = hubwriter or Hubwriter()
        self.gov = CostGovernor(goal)
        self.events: list[tuple] = []

    def _ready(self):
        done = {t.task_id for t in self.tasks if t.status == TaskStatus.ACCEPTED}
        return next((t for t in self.tasks if t.status == TaskStatus.QUEUED and set(t.depends_on) <= done), None)

    def run(self) -> dict:
        while (task := self._ready()) is not None:   # continuation = event of last delta
            self._step(task)
            if self.goal.status != GoalStatus.WORKING:
                break
        if self.goal.status == GoalStatus.WORKING:
            ok = all(t.status == TaskStatus.ACCEPTED for t in self.tasks)
            self.goal.status = GoalStatus.DONE if ok else GoalStatus.FAILED
        return board(self.goal, self.tasks, self.gov, self.hub.deltas)

    def _step(self, task: Task) -> None:
        hits = gate_hits(task, self.goal)
        if hits:
            task.status = TaskStatus.NEEDS_HUMAN
            self.goal.status = GoalStatus.NEEDS_YOU
            self.events.append(("HUMAN_GATE", task.task_id, tuple(hits)))
            return
        tried = []
        while task.attempts < MAX_ATTEMPTS:
            try:
                prof = route(task, [w.profile for w in self.workers.values()], self.gov)
            except NoWorker:
                break
            task.attempts += 1
            task.assigned_worker, task.status = prof.worker_id, TaskStatus.RUNNING
            contract = contract_for(task, prof.role)
            result = self.workers[prof.worker_id].run(contract, task.attempts)
            self.gov.charge(result.cost_eur)
            task.status = TaskStatus.RESULT_RECEIVED
            self.events.append(("RESULT_RECEIVED", task.task_id, task.attempts))
            ver = self.verifier.verify(contract, result)
            self.gov.charge(ver.cost_eur)
            if ver.verdict == "PASS":
                task.status = TaskStatus.VERIFIED
            try:
                self.hub.accept(contract, result, ver)
            except HubwriterRejected as e:
                prof.rejected += 1
                task.status = TaskStatus.REJECTED
                self.events.append(("REJECTED", task.task_id, e.code))
                if e.code == "SCOPE_ESCALATION":
                    break
                task.status = TaskStatus.QUEUED
                continue
            prof.verified += 1
            self.gov.verified_useful += 1
            task.status = TaskStatus.ACCEPTED
            self.events.append(("ACCEPTED", task.task_id, task.attempts))
            return
        task.status = TaskStatus.REJECTED
        self.goal.status = GoalStatus.FAILED
