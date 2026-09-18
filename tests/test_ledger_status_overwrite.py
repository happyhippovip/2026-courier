import pytest
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from scripts.courier_continue import update_ledger

def test_ledger_status_overwrite_fixed(tmp_path):
    """
    PROVE: update_ledger does not unconditionally overwrite STATUS="BLOCKED"
    with "READY" when a concurrent task succeeds without a new blocker.
    """
    ledger_path = tmp_path / "agent_handoff_ledger.json"
    
    # Initial state: already blocked
    record = {
        "PROJECT": "Courier",
        "GOAL": "TEST",
        "STATUS": "BLOCKED",
        "FIRST_CAUSAL_BLOCKER": "PREVIOUS_FAILURE",
        "PROVEN_EDGES": [],
        "UNPROVEN_EDGES": ["EDGE_A", "EDGE_B"],
        "LAST_EVIDENCE": []
    }
    
    bundle = {
        "record": record,
        "revision": 1,
        "acceptance_guard": {
            "binding": {"current_sha": "test", "runtime_identity": "test"},
            "evidence": [],
            "acceptance_predicate": {"results": {}}
        }
    }
    
    # Task B succeeds (no new blocker, removes itself from unproven)
    with open(ledger_path, "w") as f:
        json.dump(bundle, f)
        
    import json as json_lib
    
    # Mock 'update' function to return what it would update
    from unittest.mock import patch
    with patch("scripts.courier_continue.update") as mock_update:
        mock_update.return_value = bundle # just dummy return
        
        update_ledger(ledger_path, "EDGE_B", None, bundle)
        
        # Check what was passed to updates
        updates_arg = mock_update.call_args[0][2]
        assert updates_arg["STATUS"] == "BLOCKED", "STATUS must not be overwritten to READY if FIRST_CAUSAL_BLOCKER is active"

