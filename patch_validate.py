import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

old_if = """        if not isinstance(item, dict) or not set(item).issubset({
            "source_url",
            "source_type",
            "observed_at",
            "evidence_sha",
            "runtime_binding",
            "validity",
            "reason",
            "producer_id",
            "verifier_id",
            "result_sha256"
        }) or not {"source_url", "source_type", "observed_at", "evidence_sha", "runtime_binding", "validity", "reason", "result_sha256"}.issubset(set(item)):"""

new_if = """        if not isinstance(item, dict) or not set(item).issubset({
            "source_url", "source_type", "observed_at", "evidence_sha",
            "runtime_binding", "validity", "reason", "producer_id", "verifier_id", "result_sha256"
        }) or not {"source_url", "source_type", "observed_at", "evidence_sha", "runtime_binding", "validity", "reason"}.issubset(set(item)):"""

code = code.replace(old_if, new_if)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
