"""Tests for courier_core.work_stealing - Cross-Worker Work Stealing & Load Balancer."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.work_stealing import (
    WorkStealingCluster,
    StealableTask,
    WorkerNodeDescriptor,
    NoStealableTaskError,
    IncompatibleCapabilityError,
    CapacityExceededError,
    StaleFencingTokenError,
)


@pytest.fixture
def cluster() -> WorkStealingCluster:
    c = WorkStealingCluster()
    c.register_worker("worker-a", capacity=4, capabilities={"windows", "cpu"})
    c.register_worker("worker-b", capacity=4, capabilities={"windows", "cpu"})
    return c


def test_basic_work_stealing_between_workers(cluster: WorkStealingCluster):
    # Enqueue 4 tasks onto worker-a
    for i in range(4):
        t = StealableTask(task_id=f"t-{i}", owner="worker-a", required_capabilities={"cpu"})
        cluster.enqueue_task("worker-a", t)

    assert cluster.get_worker("worker-a").ready_count == 4
    assert cluster.get_worker("worker-b").ready_count == 0

    # Worker-b steals 1 task from worker-a
    stolen = cluster.steal_task(stealer_id="worker-b", victim_id="worker-a")
    assert stolen is not None
    assert stolen.owner == "worker-b"
    assert stolen.fencing_token == 1

    # Queues updated
    assert cluster.get_worker("worker-a").ready_count == 3
    assert cluster.get_worker("worker-b").ready_count == 1
    assert cluster.get_worker("worker-b").ready_tasks[0].task_id == stolen.task_id


def test_protection_of_running_tasks(cluster: WorkStealingCluster):
    t = StealableTask(task_id="t-running", owner="worker-a", required_capabilities={"cpu"})
    cluster.enqueue_task("worker-a", t)
    cluster.start_task("worker-a", "t-running")

    assert cluster.get_worker("worker-a").running_count == 1
    assert cluster.get_worker("worker-a").ready_count == 0

    # Worker-b attempts to steal; running task cannot be stolen
    with pytest.raises(NoStealableTaskError):
        cluster.steal_task(stealer_id="worker-b", victim_id="worker-a")


def test_capability_matching_filter(cluster: WorkStealingCluster):
    cluster.register_worker("worker-gpu", capacity=4, capabilities={"windows", "gpu"})

    t_gpu = StealableTask(task_id="t-gpu-heavy", owner="worker-gpu", required_capabilities={"gpu"})
    cluster.enqueue_task("worker-gpu", t_gpu)

    # Worker-a only has {"windows", "cpu"} -> steal should fail due to missing "gpu"
    with pytest.raises(IncompatibleCapabilityError):
        cluster.steal_task(stealer_id="worker-a", victim_id="worker-gpu")

    # Task remains on worker-gpu
    assert cluster.get_worker("worker-gpu").ready_count == 1


def test_capacity_limit_enforcement(cluster: WorkStealingCluster):
    # Worker-b has capacity 4. Fill worker-b with 4 tasks
    for i in range(4):
        t = StealableTask(task_id=f"tb-{i}", owner="worker-b", required_capabilities={"cpu"})
        cluster.enqueue_task("worker-b", t)

    # Worker-a has 2 tasks
    for i in range(2):
        t = StealableTask(task_id=f"ta-{i}", owner="worker-a", required_capabilities={"cpu"})
        cluster.enqueue_task("worker-a", t)

    # Worker-b is full -> cannot steal
    with pytest.raises(CapacityExceededError):
        cluster.steal_task(stealer_id="worker-b", victim_id="worker-a")


def test_cluster_automatic_rebalance(cluster: WorkStealingCluster):
    # Worker-a has 6 tasks, worker-b has 0
    for i in range(6):
        t = StealableTask(task_id=f"t-{i}", owner="worker-a", required_capabilities={"cpu"})
        cluster.enqueue_task("worker-a", t)

    transferred = cluster.rebalance()
    assert transferred == 3  # (6 - 0) // 2

    assert cluster.get_worker("worker-a").ready_count == 3
    assert cluster.get_worker("worker-b").ready_count == 3


def test_double_steal_and_fencing_safety(cluster: WorkStealingCluster):
    t = StealableTask(task_id="t-fence", owner="worker-a", required_capabilities={"cpu"})
    cluster.enqueue_task("worker-a", t)

    # Stolen by worker-b -> token becomes 1
    stolen = cluster.steal_task("worker-b", "worker-a")
    assert stolen.fencing_token == 1

    # Victim worker-a tries to claim or execute task with old fencing token 0 -> rejected
    with pytest.raises(StaleFencingTokenError):
        cluster.verify_execution_token(task_id="t-fence", worker_id="worker-a", token=0)

    # Worker-b with token 1 is accepted
    assert cluster.verify_execution_token(task_id="t-fence", worker_id="worker-b", token=1) is True


def test_cli_work_stealing(capsys, monkeypatch):
    from courier_core.work_stealing import main

    # Register workers
    monkeypatch.setattr(
        "sys.argv",
        ["work_stealing.py", "register", "--worker-id", "w-cli-1", "--capacity", "4", "--capabilities", "cpu,windows"],
    )
    main()

    # Enqueue task
    monkeypatch.setattr(
        "sys.argv",
        ["work_stealing.py", "enqueue", "--worker-id", "w-cli-1", "--task-id", "t-cli-100", "--capabilities", "cpu"],
    )
    main()

    # Status
    monkeypatch.setattr(
        "sys.argv",
        ["work_stealing.py", "status"],
    )
    main()
    out = capsys.readouterr().out
    assert "w-cli-1" in out
    assert "t-cli-100" in out
