import unittest
from tests.test_write_reliability import TestWriteReliability

def print_result():
    t = TestWriteReliability("test_e10_second_attempt_human_gate")
    t.setUp()
    def mock_dispatch(agent, env, adp):
        t.dispatch_count += 1
        print("MOCK DISPATCH", t.dispatch_count)
        if t.dispatch_count == 1:
            return {"dispatched_to": agent, "result_path": "dummy.json", "ack_path": "a.json", "envelope_path": "e.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "PASS"}}}
        else:
            return {"dispatched_to": agent, "result_path": "dummy.json", "ack_path": "a.json", "envelope_path": "e.json", "route": agent, "result": {"status": "HUMAN_GATE", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "result_fingerprint": "mock_fp", "payload": {"verdict": "HUMAN_GATE"}, "error_type": "AUTHENTICATION_REQUIRED"}}
    t.dispatcher.adapter_boundary.dispatch = mock_dispatch
    res = t.dispatcher.process_next_mission("founder")
    print("RESULT", res)
    print("COUNT", t.dispatch_count)
print_result()
