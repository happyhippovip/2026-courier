import sys
content = open("tests/test_agent_handoff_ledger.py").read()
content = content.replace(
'''            landed2["evidence"].append(proof2)
            landed2["evidence"][0]["validity"] = "STALE"
            landed2["evidence"][1]["validity"] = "STALE"''',
'''            landed2["evidence"][1] = proof2
            landed2["evidence"][0]["validity"] = "STALE"
            landed2["evidence"][1]["validity"] = "STALE"''')
open("tests/test_agent_handoff_ledger.py", "w").write(content)
