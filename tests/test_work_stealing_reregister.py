"""Work-stealing ownership survives re-register; task_ids stay unique.

Covers courier_core/work_stealing.py register_worker + enqueue_task:
re-registering a worker updates capacity/capabilities in place without
wiping owned queues; a duplicate task_id is rejected.
"""
import pytest

from courier_core.work_stealing import StealableTask, WorkStealingCluster


def test_reregister_preserves_queues_and_registry():
    cluster = WorkStealingCluster()
    cluster.register_worker("w1", capacity=4, capabilities={"cpu"})
    cluster.enqueue_task("w1", StealableTask(task_id="t-ready", owner="w1"))
    cluster.enqueue_task("w1", StealableTask(task_id="t-run", owner="w1"))
    cluster.start_task("w1", "t-run")
    node = cluster.register_worker("w1", capacity=8, capabilities={"cpu", "gpu"})
    assert node.capacity == 8
    assert node.capabilities == {"cpu", "gpu"}
    assert [t.task_id for t in node.ready_tasks] == ["t-ready"]
    assert list(node.running_tasks) == ["t-run"]
    assert cluster.task_registry["t-ready"].owner == "w1"
    assert cluster.task_registry["t-run"].owner == "w1"


def test_duplicate_task_id_rejected():
    cluster = WorkStealingCluster()
    cluster.register_worker("w1")
    cluster.register_worker("w2")
    cluster.enqueue_task("w1", StealableTask(task_id="t-dup", owner="w1"))
    with pytest.raises(KeyError):
        cluster.enqueue_task("w2", StealableTask(task_id="t-dup", owner="w2"))
    assert cluster.task_registry["t-dup"].owner == "w1"
