import re

with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

# Change _verify_attestation to return a dict or None
new_func = """
_attestation_resolver = None

def _verify_attestation(url: str):
    if _attestation_resolver:
        return _attestation_resolver(url)
    try:
        import requests
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None
"""

code = re.sub(
    r'_attestation_resolver = None\s+def _verify_attestation\(url: str, expected_sha256: str\) -> bool:.*?except Exception:\s+return False',
    new_func.strip(),
    code,
    flags=re.DOTALL
)

# Fix has_physical_proof logic
# We need to call _verify_attestation(url) and then check the receipt
# Wait, inside any(...) we can't do assignment easily in Python without walrus (:=) and this is python 3.9 so walrus is allowed!
# But let's write it carefully. We can map over the evidence.
code = code.replace(
    '_verify_attestation(e.get("source_url", ""), e.get("result_sha256", "")) and \\',
    '(receipt := _verify_attestation(e.get("source_url", ""))) and \\\n            receipt.get("verdict") == "PASS" and \\\n            receipt.get("result_sha256") == e.get("result_sha256") and \\\n            receipt.get("producer_principal") == e.get("producer_id") and \\\n            receipt.get("verifier_principal") == e.get("verifier_id") and \\\n            receipt.get("binding", {}).get("sha") == e.get("evidence_sha") and \\\n            receipt.get("binding", {}).get("runtime") == e.get("runtime_binding") and \\'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
