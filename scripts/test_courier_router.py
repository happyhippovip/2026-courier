from courier_admission_control import TaskPacket
from courier_router import WorkerTarget, CapabilityCostRouter

def test_routing_selects_cheapest_eligible():
    router = CapabilityCostRouter()
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=[],
        required_platform="any", required_capability="python", logical_scope="R",
        writer_required=False, budget=5.0, result_contract="none", human_gate_class="NONE"
    )
    
    targets = [
        WorkerTarget("expensive_mac", "darwin", ["python"], 2.0, 0, 1),
        WorkerTarget("cheap_linux", "linux", ["python"], 0.5, 0, 1),
        WorkerTarget("busy_cheap", "linux", ["python"], 0.1, 1, 1), # Full
        WorkerTarget("no_python", "windows", ["bash"], 0.0, 0, 1)
    ]
    
    selected = router.route(packet, targets)
    assert selected is not None
    assert selected.target_id == "cheap_linux"

def test_routing_respects_platform():
    router = CapabilityCostRouter()
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=[],
        required_platform="windows", required_capability="any", logical_scope="R",
        writer_required=False, budget=5.0, result_contract="none", human_gate_class="NONE"
    )
    
    targets = [
        WorkerTarget("mac_worker", "darwin", ["python"], 0.5, 0, 1),
        WorkerTarget("win_worker", "win32", ["python"], 1.0, 0, 1),
    ]
    
    selected = router.route(packet, targets)
    assert selected is not None
    assert selected.target_id == "win_worker"

def test_routing_no_eligible():
    router = CapabilityCostRouter()
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=[],
        required_platform="any", required_capability="rust", logical_scope="R",
        writer_required=False, budget=5.0, result_contract="none", human_gate_class="NONE"
    )
    
    targets = [
        WorkerTarget("t1", "darwin", ["python"], 1.0, 0, 1)
    ]
    
    selected = router.route(packet, targets)
    assert selected is None
