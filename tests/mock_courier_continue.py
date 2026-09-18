import sys
import os
from pathlib import Path

repo_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(repo_dir))

from scripts import agent_handoff_ledger

def mock_resolver(url):
    return {
        "verdict": "PASS",
        "producer_principal": "producer_1",
        "verifier_principal": "verifier_1",
        "result_sha256": "0" * 40,
        "goal_id": os.environ.get("MOCK_GOAL_ID", "test-goal"),
        "binding": {
            "sha": "0" * 40,
            "runtime": "0" * 40
        },
        "sha": "0" * 40,
        "runtime": "0" * 40
    }

agent_handoff_ledger._attestation_resolver = mock_resolver

from scripts.courier_continue import main
if __name__ == "__main__":
    main()
