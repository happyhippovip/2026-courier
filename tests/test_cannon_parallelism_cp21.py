"""Tests for CP-21 / CQ-21 / GB-CANNON-01: Cannon Parallelism Planner & Admissible Task-Worker Matching

Verifies:
1. 1 task / 10 workers yields 1 admissible pairing (no fake parallelism).
2. Incompatible pairings yield 0 (capability mismatch blocks scheduling).
3. Scope overlap and resource contention limits parallelism even with free workers.
4. Shared provider capacity restricts concurrency to pool bounds.
5. Independent admissible tasks execute in parallel.
6. Evidence generated with ['ready-frontier', 'worker-capabilities', 'shared-capacity'].
"""

import pytest

from courier_core.cannon_parallelism_planner import (
    CannonParallelismPlanner,
    ReadyTask,
    RejectionReason,
    WorkerNode,
)


def test_one_task_ten_workers_yields_one():
    planner = CannonParallelismPlanner()

    tasks = [
        ReadyTask(task_id="task-01", required_capabilities={"python"}, priority=10),
    ]

    workers = [
        WorkerNode(worker_id=f"worker-{i:02d}", supported_capabilities={"python"})
        for i in range(10)
    ]

    plan = planner.compute_plan(tasks, workers)

    assert plan.naive_parallelism == 1
    assert plan.admissible_parallelism == 1
    assert len(plan.assigned_pairings) == 1
    assert plan.assigned_pairings[0].task_id == "task-01"
    assert len(plan.unpaired_workers) == 9
    assert len(plan.unpaired_tasks) == 0


def test_incompatible_pairings_yield_zero():
    planner = CannonParallelismPlanner()

    # 5 tasks requiring specialized capabilities
    tasks = [
        ReadyTask(task_id=f"task-{i}", required_capabilities={"docker", "gpu_cuda"})
        for i in range(5)
    ]

    # 10 workers supporting only basic python
    workers = [
        WorkerNode(worker_id=f"worker-{i}", supported_capabilities={"python", "bash"})
        for i in range(10)
    ]

    plan = planner.compute_plan(tasks, workers)

    # Naive heuristic incorrectly thinks 5 tasks can run
    assert plan.naive_parallelism == 5
    # Admissible planner correctly computes 0
    assert plan.admissible_parallelism == 0
    assert len(plan.assigned_pairings) == 0
    assert len(plan.unpaired_tasks) == 5

    for tid, reason in plan.unpaired_tasks.items():
        assert RejectionReason.NO_CAPABLE_WORKER.value in reason


def test_scope_overlap_and_resource_contention_blocks_parallelism():
    planner = CannonParallelismPlanner()

    # 2 tasks requiring the SAME exclusive resource lock
    tasks = [
        ReadyTask(
            task_id="task-migration-a",
            required_capabilities={"python"},
            required_resources={"lock:database_schema.sql"},
            priority=10,
        ),
        ReadyTask(
            task_id="task-migration-b",
            required_capabilities={"python"},
            required_resources={"lock:database_schema.sql"},
            priority=5,
        ),
    ]

    # 2 capable available workers
    workers = [
        WorkerNode(worker_id="w-01", supported_capabilities={"python"}),
        WorkerNode(worker_id="w-02", supported_capabilities={"python"}),
    ]

    plan = planner.compute_plan(tasks, workers)

    # Naive is 2, but admissible is 1 due to resource conflict
    assert plan.naive_parallelism == 2
    assert plan.admissible_parallelism == 1
    assert len(plan.assigned_pairings) == 1
    assert plan.assigned_pairings[0].task_id == "task-migration-a"

    # Task B rejected with resource contention
    assert "task-migration-b" in plan.unpaired_tasks
    assert RejectionReason.RESOURCE_CONTENTION.value in plan.unpaired_tasks["task-migration-b"]


def test_shared_provider_capacity_limits_parallelism():
    # Gemini pool capped at 2
    planner = CannonParallelismPlanner(provider_capacities={"gemini": 2})

    tasks = [
        ReadyTask(task_id=f"task-gen-{i}", required_capabilities={"gemini_api"}, provider="gemini", priority=10 - i)
        for i in range(5)
    ]

    workers = [
        WorkerNode(worker_id=f"worker-g-{i}", supported_capabilities={"gemini_api"}, provider="gemini")
        for i in range(5)
    ]

    plan = planner.compute_plan(tasks, workers)

    # Naive is 5, but provider pool cap limits to 2
    assert plan.naive_parallelism == 5
    assert plan.admissible_parallelism == 2
    assert len(plan.assigned_pairings) == 2
    assert plan.shared_capacity_headroom["gemini"] == 0

    # Remaining 3 tasks throttled
    assert len(plan.unpaired_tasks) == 3
    for tid in ("task-gen-2", "task-gen-3", "task-gen-4"):
        assert RejectionReason.PROVIDER_CAPACITY_EXHAUSTED.value in plan.unpaired_tasks[tid]


def test_independent_admissible_tasks_run_in_parallel():
    planner = CannonParallelismPlanner(provider_capacities={"local": 5})

    # 3 independent tasks with disjoint resource scopes
    tasks = [
        ReadyTask(task_id="task-alpha", required_capabilities={"python"}, required_resources={"file:a.py"}, provider="local"),
        ReadyTask(task_id="task-beta", required_capabilities={"powershell"}, required_resources={"file:b.ps1"}, provider="local"),
        ReadyTask(task_id="task-gamma", required_capabilities={"git"}, required_resources={"file:c.md"}, provider="local"),
    ]

    workers = [
        WorkerNode(worker_id="w-py", supported_capabilities={"python"}, provider="local"),
        WorkerNode(worker_id="w-ps", supported_capabilities={"powershell"}, provider="local"),
        WorkerNode(worker_id="w-git", supported_capabilities={"git"}, provider="local"),
    ]

    plan = planner.compute_plan(tasks, workers)

    assert plan.admissible_parallelism == 3
    assert len(plan.assigned_pairings) == 3
    assert len(plan.unpaired_tasks) == 0
    assert len(plan.unpaired_workers) == 0


def test_evidence_generation():
    planner = CannonParallelismPlanner()

    tasks = [
        ReadyTask(task_id="t1", required_capabilities={"python"}),
    ]
    workers = [
        WorkerNode(worker_id="w1", supported_capabilities={"python"}),
    ]

    evidence = planner.generate_parallelism_evidence(tasks, workers)

    assert evidence["required_evidence"] == ["ready-frontier", "worker-capabilities", "shared-capacity"]
    assert evidence["ready-frontier"]["task_count"] == 1
    assert evidence["worker-capabilities"]["worker_count"] == 1
    assert evidence["shared-capacity"]["admissible_parallelism"] == 1
