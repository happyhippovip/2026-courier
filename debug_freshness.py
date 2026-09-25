import re
with open("tests/test_ledger_freshness_binding_epoch.py", "r") as f:
    content = f.read()

replacement = """        result = update(path, 1, {"TASKS_COMPLETED": 4, "STATUS": "DONE"}, "writer-b", 5.0)
        import json
        print(json.dumps(result, indent=2))
        assert result["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"
"""
content = content.replace('        result = update(path, 1, {"TASKS_COMPLETED": 4, "STATUS": "DONE"}, "writer-b", 5.0)\n        assert result["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"', replacement)

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
