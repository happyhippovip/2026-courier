import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    content = f.read()

replacement = """                receipt = _verify_attestation(e.get("source_url"))
                if receipt and receipt.get("verdict") == "PASS":
                    with open("/tmp/debug_receipt.txt", "a") as df:
                        df.write(f"PRODUCER: {receipt.get('producer_principal')} == {e.get('producer_id')} -> {receipt.get('producer_principal') == e.get('producer_id')}\\n")
                        df.write(f"VERIFIER: {receipt.get('verifier_principal')} == {e.get('verifier_id')} -> {receipt.get('verifier_principal') == e.get('verifier_id')}\\n")
                        df.write(f"SHA: {receipt.get('result_sha256')} == {e.get('result_sha256')} -> {receipt.get('result_sha256') == e.get('result_sha256')}\\n")
                        df.write(f"GOAL: {receipt.get('goal_id')} == {bundle.get('record', {}).get('GOAL')} -> {receipt.get('goal_id') == bundle.get('record', {}).get('GOAL')}\\n")
                        b = receipt.get("binding", {})
                        df.write(f"BSHA: {b.get('sha')} == {guard['binding']['current_sha']} -> {b.get('sha') == guard['binding']['current_sha']}\\n")
                        df.write(f"BRUN: {b.get('runtime')} == {guard['binding']['runtime_identity']} -> {b.get('runtime') == guard['binding']['runtime_identity']}\\n")
"""
content = re.sub(r'                receipt = _verify_attestation\(e\.get\(\"source_url\"\)\)\n                if receipt and receipt\.get\(\"verdict\"\) == \"PASS\":', replacement, content)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(content)
