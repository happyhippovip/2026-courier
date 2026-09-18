import pytest
import tempfile
import json
from pathlib import Path
from scripts.agent_handoff_ledger import initialize, update, LedgerError, RECORD_FIELDS

def test_duplicate_semantics_contract():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "test_ledger.json"
        
        record = {k: ("[]" if "EDGES" in k or k in ("ACTIVE_WRITERS", "COLLISION_SCOPE", "LAST_EVIDENCE") else 
                      ("UNKNOWN" if k in ("CLEAN_IDLE", "QUEUE_INDEPENDENT") else 
                      (0 if k in ("GOALS_SUBMITTED", "TASKS_COMPLETED", "WORKERS_USED", "USER_CONTINUE_MESSAGES", "MANUAL_PROCESS_RESTARTS", "DUPLICATE_EXTERNAL_EFFECTS", "TEMP_TASK_PROCESSES_AFTER_DONE") else "none")))
                  for k in RECORD_FIELDS}
        record["PROVEN_EDGES"] = []
        record["UNPROVEN_EDGES"] = []
        record["ACTIVE_WRITERS"] = []
        record["COLLISION_SCOPE"] = []
        record["LAST_EVIDENCE"] = []
        record["CURRENT_SHA"] = "0"*40
        record["BRANCH"] = "main"
        record["RUNTIME_IDENTITY"] = "test"
        
        guard = {
            "acceptance_predicate": {
                "name": "Global-Stop",
                "version": "1.0",
                "results": {
                    "ISSUE_STATE": {
                        "status": "PASS",
                        "observed_value": "NO_FURTHER_ACTION",
                        "evidence_urls": ["https://example.com/evidence"]
                    }
                },
                "required_results": ["ISSUE_STATE"]
            },
            "binding": {
                "branch": "main",
                "current_sha": "0"*40,
                "runtime_identity": "test"
            },
            "evidence": [
                {
                    "source_url": "https://example.com/evidence",
                    "source_type": "MACHINE_ARTIFACT",
                    "observed_at": "2026-09-18T00:00:00Z",
                    "evidence_sha": "0"*40,
                    "runtime_binding": "test",
                    "validity": "VALID",
                    "reason": "initial"
                }
            ],
            "flow": [
                "EXECUTION",
                "EVIDENCE",
                "ACCEPTANCE_GUARD",
                "LEDGER_TRANSITION",
                "NEXT_EXECUTABLE_ACTION"
            ],
            "transition_state": "PROVISIONAL",
            "worker_state": "IDLE/YIELDED"
        }
        
        bundle = initialize(ledger_path, record, guard, 5.0)
        
        # 1. First update to TASKS_COMPLETED=1
        bundle1 = update(ledger_path, 0, {"TASKS_COMPLETED": 1}, "test-worker", 5.0)
        assert bundle1["revision"] == 1
        
        raw_bytes = ledger_path.read_bytes()
        
        # 2. Identical same-revision replay (no meaningful change)
        with pytest.raises(LedgerError) as exc_info:
            update(ledger_path, 1, {"TASKS_COMPLETED": 1}, "test-worker", 5.0)
        assert "makes no meaningful change" in str(exc_info.value)
        assert ledger_path.read_bytes() == raw_bytes
        
        # 3. Genuine current-revision update
        bundle2 = update(ledger_path, 1, {"TASKS_COMPLETED": 5}, "test-worker", 5.0)
        assert bundle2["revision"] == 2
        assert bundle2["record"]["TASKS_COMPLETED"] == 5
        
        # 4. Stale contradictory write
        with pytest.raises(LedgerError) as exc_info:
            update(ledger_path, 1, {"TASKS_COMPLETED": 9}, "test-worker", 5.0)
        assert "revision conflict" in str(exc_info.value)
        
        with open(ledger_path) as f:
            final_data = json.load(f)
        assert final_data["revision"] == 2
        assert final_data["record"]["TASKS_COMPLETED"] == 5

