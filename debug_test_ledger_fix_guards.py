import re
with open("scripts/agent_handoff_ledger.py", "r") as f:
    code = f.read()

debug = """                            if not receipt:
                                print(f"DEBUG: receipt is None for {u}")
                            else:
                                print(f"DEBUG: receipt verdict is {receipt.get('verdict')}")
                                print(f"DEBUG: result_sha256 mismatch? {receipt.get('result_sha256') != e.get('result_sha256')}")
                                print(f"DEBUG: receipt: {receipt}")"""
code = code.replace(
    '                            if not receipt or receipt.get("verdict") != "PASS" or \\',
    debug + '\n                            if not receipt or receipt.get("verdict") != "PASS" or \\'
)

with open("scripts/agent_handoff_ledger.py", "w") as f:
    f.write(code)
