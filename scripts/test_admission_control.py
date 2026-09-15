from courier_admission_control import TaskPacket, HostState, PreDispatchAdmission, AdmissionResult

def test_platform_misroute_prevented():
    host = HostState(
        platform="darwin",
        capabilities=["python", "bash"],
        active_scopes=[],
        available_budget=10.0,
        unresolved_dependencies=[]
    )
    admission = PreDispatchAdmission(host)
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=[],
        required_platform="windows", required_capability="any", logical_scope="R6",
        writer_required=True, budget=1.0, result_contract="none", human_gate_class="NONE"
    )
    
    assert admission.evaluate(packet) == AdmissionResult.BLOCKED

def test_human_gate_required():
    host = HostState(platform="darwin", capabilities=[], active_scopes=[], available_budget=10.0, unresolved_dependencies=[])
    admission = PreDispatchAdmission(host)
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=[],
        required_platform="any", required_capability="any", logical_scope="A",
        writer_required=False, budget=1.0, result_contract="none", human_gate_class="REVIEW_REQUIRED"
    )
    
    assert admission.evaluate(packet) == AdmissionResult.HUMAN_REQUIRED

def test_eligible_task():
    host = HostState(platform="darwin", capabilities=["python"], active_scopes=[], available_budget=10.0, unresolved_dependencies=[])
    admission = PreDispatchAdmission(host)
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=[],
        required_platform="mac", required_capability="python", logical_scope="A",
        writer_required=True, budget=1.0, result_contract="none", human_gate_class="NONE"
    )
    
    assert admission.evaluate(packet) == AdmissionResult.ELIGIBLE
