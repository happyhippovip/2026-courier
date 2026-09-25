from scripts.courier_continue import update_ledger
from scripts.agent_handoff_ledger import load_bundle
from pathlib import Path

ledger_path = Path("agent_handoff_ledger.json")
bundle = load_bundle(ledger_path)
print("Revision before:", bundle["revision"])

new_bundle = update_ledger(ledger_path, "SALES PACKAGE", None, bundle)
print("Revision returned:", new_bundle["revision"])

bundle_after = load_bundle(ledger_path)
print("Revision on disk:", bundle_after["revision"])
