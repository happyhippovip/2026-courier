with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

bad = '''                            receipt = _verify_attestation(url)
                            if not receipt or receipt.get("verdict") != "PASS" or \\
                               receipt.get("producer_principal") != e.get("producer_id") or \\
                               receipt.get("verifier_principal") != e.get("verifier_id") or \\
                               receipt.get("result_sha256") != e.get("result_sha256"):
                                raise SelfCertificationError(f"predicate PASS requires verified receipt for {url}")'''

good = '''                            receipt = _verify_attestation(url)
                            print(f"DEBUG RECEIPT: {receipt}", flush=True)
                            print(f"DEBUG E: {e}", flush=True)
                            if not receipt or receipt.get("verdict") != "PASS" or \\
                               receipt.get("producer_principal") != e.get("producer_id") or \\
                               receipt.get("verifier_principal") != e.get("verifier_id") or \\
                               receipt.get("result_sha256") != e.get("result_sha256"):
                                raise SelfCertificationError(f"predicate PASS requires verified receipt for {url}")'''

content = content.replace(bad, good)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
