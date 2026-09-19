with open("scripts/agent_handoff_ledger.py", "r") as f:
    lines = f.readlines()

new_func = """
_attestation_resolver = None

def _verify_attestation(url: str, expected_sha256: str) -> bool:
    if _attestation_resolver:
        return _attestation_resolver(url, expected_sha256)
    try:
        import requests
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            return False
        data = resp.json()
        return data.get('verdict') == 'PASS' and data.get('result_sha256') == expected_sha256
    except Exception:
        return False
"""

# Insert at line 23
lines.insert(23, new_func)

# Now find where to insert the verify call in has_physical_proof
# It should be after e.get("validity") == "VALID" and \
for i, line in enumerate(lines):
    if 'e.get("validity") == "VALID" and \\' in line:
        lines.insert(i+1, '            _verify_attestation(e.get("source_url", ""), e.get("result_sha256", "")) and \\\n')
        break

# Now replace validate_guard
content = "".join(lines)
content = content.replace(
    '"producer_id",\n            "verifier_id"\n        }) or not {"source_url", "source_type", "observed_at", "evidence_sha", "runtime_binding", "validity", "reason"}.issubset(set(item)):',
    '"producer_id",\n            "verifier_id",\n            "result_sha256"\n        }) or not {"source_url", "source_type", "observed_at", "evidence_sha", "runtime_binding", "validity", "reason", "result_sha256"}.issubset(set(item)):'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
