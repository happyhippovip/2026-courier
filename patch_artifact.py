import re
with open("tests/test_ledger_freshness_binding_epoch.py", "r") as f:
    content = f.read()

replacement = """        "producer_id": producer,
        "verifier_id": verifier,
        "result_sha256": "fake-hash",
    }"""

content = content.replace("""        "producer_id": producer,
        "verifier_id": verifier,
    }""", replacement)

with open("tests/test_ledger_freshness_binding_epoch.py", "w") as f:
    f.write(content)
