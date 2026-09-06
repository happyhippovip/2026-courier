from tests.test_write_reliability import TestWriteReliability

t = TestWriteReliability("test_e14_cli1_no_write_retry")
t.setUp()
t.dispatcher.mission_queue.claim_next("founder")
t.dispatcher.mission_queue.transition("m1", "BLOCKED", claimed_by="founder")

t.dispatcher.mission_queue.enqueue({
    "mission_id": "m_cli1",
    "capability_required": "analysis",
    "preferred_agent": "CLI1",
    "task": {
        "action": "implement_bounded_improvement",
        "requires_write": True,
        "acceptance_criteria": {"file_exists": "effect.txt"}
    }
})

def mock_dispatch(agent, env, adp):
    print("MOCK DISPATCH E14 called with agent:", agent)
    if agent == "CLI1":
        raise RuntimeError("CLI1_READONLY_CONTRACT_VIOLATED")
    t.dispatch_count += 1
    return {"result_path": "dummy.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}

t.dispatcher.adapter_boundary.dispatch = mock_dispatch
try:
    res = t.dispatcher.process_next_mission("founder")
except Exception:
    res = {"status": "FAILED"}

print("res:", res)
print("dispatch_count:", t.dispatch_count)
