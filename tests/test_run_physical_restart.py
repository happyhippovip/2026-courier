import pytest
from pathlib import Path
import json

def test_run_physical_restart_success(tmp_path, monkeypatch):
    import scripts.run_physical_restart as script
    
    monkeypatch.setattr(script, "check_resources", lambda *args, **kwargs: True)
    monkeypatch.setattr(script, "check_port_free", lambda *args, **kwargs: True)
    
    run1_dir = tmp_path / "run1"
    run1_evidence = run1_dir / "evidence"
    run1_evidence.mkdir(parents=True)
    (run1_evidence / "run1_exit_code.txt").write_text("0")
    (run1_evidence / "run1_state_snapshot.json").write_text(json.dumps({"final_status": "SUCCESS", "payload": {}}))
    
    run1_state = run1_dir / "state"
    run1_state.mkdir(parents=True)
    (run1_state / "central_state.json").write_text(json.dumps({
        "goals": {
            "g1": {
                "goal_id": "g1",
                "status": "ACTIVE",
                "current_step_index": 1,
                "workflow_plan": [
                    {
                        "task_id": "process_a",
                        "goal_id": "g1",
                        "status": "RECONCILED",
                        "target_agent": "mac",
                        "instruction": "echo 'Process A Complete'",
                        "attempts": 1
                    },
                    {
                        "task_id": "process_b",
                        "goal_id": "g1",
                        "status": "QUEUED",
                        "target_agent": "mac",
                        "instruction": "echo 'Process B Complete'",
                        "attempts": 0
                    }
                ],
                "payload": {
                    "candidate_sha": "abcd",
                    "run_id": "RUN_2",
                    "host": "MAC",
                    "test_target": "tests/",
                    "artifacts": [{"name": "evidence.zip", "path": "evidence/"}]
                }
            }
        },
        "tasks": {
            "process_b": {
                "task_id": "process_b",
                "goal_id": "g1",
                "status": "QUEUED",
                "target_agent": "mac",
                "instruction": "echo 'Process B Complete'",
                "attempts": 0
            }
        }
    }))

    run2_evidence = tmp_path / "run2_evidence"
    
    code = script.execute_run2("abcd", str(run1_dir), str(run2_evidence), 8081)
    
    assert code == 0
    assert (run2_evidence / "run2_exit_code.txt").read_text().strip() == "0"
    
    snap = json.loads((run2_evidence / "run2_state_snapshot.json").read_text())
    assert snap["final_status"] in ("SUCCESS", "DONE")
    assert snap["initial_state"]["process_a_status"] == "COMPLETE"
    assert snap["execution_counters"]["process_a"] == 0
    assert (run2_evidence / "run2_falsifiability_hash.txt").exists()

def test_run_physical_restart_run1_fail(tmp_path, monkeypatch):
    import scripts.run_physical_restart as script
    
    monkeypatch.setattr(script, "check_resources", lambda *args, **kwargs: True)
    monkeypatch.setattr(script, "check_port_free", lambda *args, **kwargs: True)
    
    run1_dir = tmp_path / "run1_fail"
    run1_evidence = run1_dir / "evidence"
    run1_evidence.mkdir(parents=True)
    (run1_evidence / "run1_exit_code.txt").write_text("1")
    (run1_evidence / "run1_state_snapshot.json").write_text(json.dumps({"final_status": "FAIL", "payload": {}}))
    
    run2_evidence = tmp_path / "run2_evidence_fail"
    
    with pytest.raises(RuntimeError, match="RUN 1 did not PASS cleanly"):
        script.execute_run2("abcd", str(run1_dir), str(run2_evidence), 8081)

