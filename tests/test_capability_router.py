from scripts.capability_router import Capability, WorkerProfile, select_best_worker

def test_select_cheapest_qualified_worker():
    workers = [
        WorkerProfile(worker_id="gpt4", capabilities=[Capability.STRONG_CODE_WORKER, Capability.CHEAP_REASONING_WORKER], cost_per_unit=0.03),
        WorkerProfile(worker_id="gpt35", capabilities=[Capability.CHEAP_REASONING_WORKER], cost_per_unit=0.001),
        WorkerProfile(worker_id="ci_runner", capabilities=[Capability.DETERMINISTIC_CI], cost_per_unit=0.0),
    ]
    
    # Needs strong code
    best = select_best_worker([Capability.STRONG_CODE_WORKER], workers)
    assert best.worker_id == "gpt4"
    
    # Needs cheap reasoning -> should pick gpt35 because it's cheaper
    best = select_best_worker([Capability.CHEAP_REASONING_WORKER], workers)
    assert best.worker_id == "gpt35"
    
    # Needs deterministic CI
    best = select_best_worker([Capability.DETERMINISTIC_CI], workers)
    assert best.worker_id == "ci_runner"

def test_no_qualified_worker():
    workers = [
        WorkerProfile(worker_id="gpt4", capabilities=[Capability.STRONG_CODE_WORKER], cost_per_unit=0.03)
    ]
    best = select_best_worker([Capability.WINDOWS_DESKTOP_WORKER], workers)
    assert best is None

def test_ignores_unavailable_workers():
    workers = [
        WorkerProfile(worker_id="ci_fast", capabilities=[Capability.DETERMINISTIC_CI], cost_per_unit=0.0, is_available=False),
        WorkerProfile(worker_id="ci_slow", capabilities=[Capability.DETERMINISTIC_CI], cost_per_unit=0.1, is_available=True)
    ]
    best = select_best_worker([Capability.DETERMINISTIC_CI], workers)
    assert best.worker_id == "ci_slow"
