with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

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

code = code.replace(
    'MAX_EVIDENCE_AGE_SECONDS = 48 * 3600',
    'MAX_EVIDENCE_AGE_SECONDS = 48 * 3600\n' + new_func
)

# And replace `has_physical_proof` logic:
# Wait, let's just do a manual replace for the `has_physical_proof` line
old_line = 'e.get("validity") == "VALID" and \\'
new_line = 'e.get("validity") == "VALID" and \\\n            (receipt := _verify_attestation(e.get("source_url", ""))) and \\\n            receipt.get("verdict") == "PASS" and \\\n            receipt.get("result_sha256") == e.get("result_sha256") and \\\n            receipt.get("producer_principal") == e.get("producer_id") and \\\n            receipt.get("verifier_principal") == e.get("verifier_id") and \\\n            receipt.get("binding", {}).get("sha") == e.get("evidence_sha") and \\\n            receipt.get("binding", {}).get("runtime") == e.get("runtime_binding") and \\\n            receipt.get("goal_id") == bundle["record"]["GOAL"] and \\'

code = code.replace(old_line, new_line)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
