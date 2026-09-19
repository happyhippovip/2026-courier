with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

code = code.replace(
    'print(f"DEBUG: goal={bundle.get(\\"record\\", {}).get(\\"GOAL\\")} e={e.get(\\"producer_id\\")} == {receipt.get(\\"producer_principal\\")} and {e.get(\\"verifier_id\\")} == {receipt.get(\\"verifier_principal\\")} and {e.get(\\"result_sha256\\")} == {receipt.get(\\"result_sha256\\")}"); raise SelfCertificationError(f"predicate PASS requires verified receipt for {url}")',
    'print(f"DEBUG: goal_in_record={bundle.get(\'record\', {}).get(\'GOAL\')} goal_in_receipt={receipt.get(\'goal_id\')} receipt_prod={receipt.get(\'producer_principal\')} e_prod={e.get(\'producer_id\')} e_sha={e.get(\'result_sha256\')} r_sha={receipt.get(\'result_sha256\')}"); raise SelfCertificationError(f"predicate PASS requires verified receipt for {url}")'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
