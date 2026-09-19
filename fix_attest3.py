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
    'MAX_EVIDENCE_AGE_SECONDS = 172800',
    'MAX_EVIDENCE_AGE_SECONDS = 172800\n' + new_func
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
