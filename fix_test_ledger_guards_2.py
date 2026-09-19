import re

with open("tests/test_ledger_fix_guards.py", "r") as f:
    code = f.read()

old_fr = """        g1 = with_pass(guard(), ART_URL + "-fr")
        g1["evidence"].append(artifact("-fr", "fresh-prod", "fresh-ver"))
        ledger.update(path, 0, {"TASKS_COMPLETED": 1}, "w1", 5.0, g1)
        b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "w2", 5.0)"""

new_fr = """        g1 = guard()
        g1["evidence"].append(artifact("-fr", "fresh-prod", "fresh-ver"))
        b1 = ledger.update(path, 0, {"TASKS_COMPLETED": 1}, "w1", 5.0, g1)
        g2 = with_pass(b1["acceptance_guard"], ART_URL + "-fr")
        b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "w2", 5.0, g2)"""
code = code.replace(old_fr, new_fr)

with open("tests/test_ledger_fix_guards.py", "w") as f:
    f.write(code)

