import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

# 1. Modify _verify_attestation
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
code = re.sub(
    r'def _verify_attestation\(url: str\) -> bool:.*?except Exception:\n        return False',
    new_func.strip(),
    code,
    flags=re.DOTALL
)

# 2. Modify validate_guard to allow and require result_sha256
code = code.replace(
    '"producer_id",\n            "verifier_id"\n        }) or not {"source_url", "source_type", "observed_at", "evidence_sha", "runtime_binding", "validity", "reason"}.issubset(set(item)):',
    '"producer_id",\n            "verifier_id",\n            "result_sha256"\n        }) or not {"source_url", "source_type", "observed_at", "evidence_sha", "runtime_binding", "validity", "reason", "result_sha256"}.issubset(set(item)):'
)

# 3. Pass result_sha256 to _verify_attestation
code = code.replace(
    '_verify_attestation(e.get("source_url", "")) and \\',
    '_verify_attestation(e.get("source_url", ""), e.get("result_sha256", "")) and \\'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
