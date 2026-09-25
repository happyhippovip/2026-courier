from scripts.courier_continue import check_freshness
from scripts.agent_handoff_ledger import load_bundle
import sys
from pathlib import Path

ledger_path = Path("agent_handoff_ledger.json")
try:
    check_freshness(ledger_path, "agent/mac-cannon-v1-fixes", "b459ff11249d4b164ca851c0b1c441131eb4ff6b")
    print("Success")
except Exception as e:
    print(repr(e))
