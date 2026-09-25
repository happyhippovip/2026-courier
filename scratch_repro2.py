from scripts.courier_continue import update_ledger
from scripts.agent_handoff_ledger import load_bundle
from pathlib import Path

ledger_path = Path("agent_handoff_ledger.json")
bundle = load_bundle(ledger_path)
print("Before update, unproven edges:", len(bundle["record"].get("UNPROVEN_EDGES", [])))

update_ledger(ledger_path, "SALES PACKAGE", None, bundle)
print("Success")
