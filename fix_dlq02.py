import re

with open("tests/test_DLQ02_freshness_bound.py", "r") as f:
    code = f.read()

# Fix for test_dlq02_stale_evidence_rejected
code = code.replace(
'''    g1 = base_guard()
    g1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS", "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/stale-1"],
    }''',
'''    g1 = base_guard()
    g1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "UNKNOWN", "observed_value": "BOUND",
        "evidence_urls": ["https://github.com/example/project/actions/runs/stale-1"],
    }'''
)

code = code.replace(
'''    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0)
    assert b2["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    assert b2["record"]["CLEAN_IDLE"] == "NO"''',
'''    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    g2 = dict(b1["acceptance_guard"])
    import copy
    g2 = copy.deepcopy(b1["acceptance_guard"])
    g2["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "PASS"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0, g2)
    assert b2["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    assert b2["record"]["CLEAN_IDLE"] == "NO"'''
)

code = code.replace(
'''    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0)
    assert b2["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"
    assert b2["record"]["CLEAN_IDLE"] == "YES"''',
'''    b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
    assert b1["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    
    g2 = dict(b1["acceptance_guard"])
    import copy
    g2 = copy.deepcopy(b1["acceptance_guard"])
    g2["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "PASS"
    
    b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0, g2)
    assert b2["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"
    assert b2["record"]["CLEAN_IDLE"] == "YES"'''
)

with open("tests/test_DLQ02_freshness_bound.py", "w") as f:
    f.write(code)
