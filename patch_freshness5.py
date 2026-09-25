import re
with open("tests/test_ledger_freshness_binding_epoch.py", "r") as f:
    content = f.read()

replacement = """        result = update(path, 1, {"TASKS_COMPLETED": 4, "STATUS": "DONE"}, "writer-b", 5.0)
        
        # Verify receipt right here
        import scripts.agent_handoff_ledger as ahl
        print("Mock resolver direct test:", ahl._verify_attestation("https://test.com/47h"))
        
        assert result["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED\""""

content = re.sub(r'        result = update\(path, 1, \{\"TASKS_COMPLETED\": 4, \"STATUS\": \"DONE\"\}, \"writer-b\", 5\.0\)\n        print\(\"MOCK VERIFY CALLED:\", mock_verify\.called\)\n        assert result\[\"acceptance_guard\"\]\[\"transition_state\"\] == \"CANONICAL_ACCEPTED\"', replacement, content)

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
