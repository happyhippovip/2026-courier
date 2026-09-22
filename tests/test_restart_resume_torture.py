import json
import os
import subprocess
import sys
from pathlib import Path
from test_queue_independence import setup_ledger # reuse ledger setup from the other test!

def test_restart_resume_torture(tmp_path):
    torture_task = "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION"
    
    # We put everything in proven_edges except our torture_task to isolate it
    ledger_path = setup_ledger(
        tmp_path,
        unproven_edges=[torture_task],
        blocker="NONE",
        proven_edges=[
            'LEDGER/HANDOFF', 'PR41 ACCEPTANCE', 
            'RELEASE - SAFE_AUTOMATABLE_PREPARATION', 
            'RELEASE - IRREVERSIBLE_HUMAN_ACTION', 'PUBLIC DEPLOYMENT - IRREVERSIBLE_HUMAN_ACTION', 
            'PUBLICATION VERIFICATION', 'PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION', 
 'PILOT INTAKE - IRREVERSIBLE_HUMAN_ACTION', 
            'SALES PACKAGE', 'FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION', 
 'FIRST PILOT - IRREVERSIBLE_HUMAN_ACTION', 
            'PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION', 
 
            'PAYMENT ONLY WHEN ACTUALLY REQUIRED - IRREVERSIBLE_HUMAN_ACTION', 
            'POST-PILOT HARDENING', 
            'EXTERNAL_PUBLICATION - IRREVERSIBLE_HUMAN_ACTION', 
            'ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION', 
 
            'ONBOARD_FIRST_PILOT_CUSTOMER - IRREVERSIBLE_HUMAN_ACTION',
            'PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION',
],
    )
    
    env = os.environ.copy()
    env["MOCK_GOAL_ID"] = "QUEUE-INDEPENDENT-TEST"
    env["MOCK_LEDGER"] = str(ledger_path)
    env["MOCK_BRANCH"] = "test-branch"
    env["MOCK_SHA"] = "0000000000000000000000000000000000000000"
    env["MOCK_TORTURE_TASK"] = torture_task
    
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "tests" / "mock_courier_continue.py"
    
    # Run #1: Motor starts, hits torture task, does step 1, hard crashes (exit 99)
    res1 = subprocess.run([sys.executable, str(script), "--run"], env=env, cwd=str(tmp_path), capture_output=True, text=True)
    assert res1.returncode == 99, f"Expected motor to crash with 99, got {res1.returncode}. Output:\n{res1.stdout}\n{res1.stderr}"
    
    # Verify checkpoint 1
    durable_1 = tmp_path / "torture_durable_1.txt"
    assert durable_1.exists()
    assert durable_1.read_text() == "X", "Durable step 1 should have exactly one X"
    
    state_file = tmp_path / "torture_state.txt"
    assert state_file.read_text() == "1"
    
    # Run #2: Motor restarts. Resume torture task from state 1.
    res2 = subprocess.run([sys.executable, str(script), "--run"], env=env, cwd=str(tmp_path), capture_output=True, text=True)
    assert res2.returncode == 0, f"Expected motor to finish successfully, got {res2.returncode}. Output:\n{res2.stdout}\n{res2.stderr}"
    
    # Verify step 1 was not replayed
    assert durable_1.read_text() == "X", "Durable step 1 MUST NOT be replayed (should still be exactly 'X')"
    
    # Verify step 2 was completed
    durable_2 = tmp_path / "torture_durable_2.txt"
    assert durable_2.exists()
    assert durable_2.read_text() == "Y", "Durable step 2 should have exactly one Y"
    
    assert state_file.read_text() == "2"
    
    # Verify task successfully completed in the ledger
    with open(ledger_path) as f:
        data = json.load(f)
    
    unproven = data["record"]["UNPROVEN_EDGES"]
    if torture_task in unproven: open("res2_output.txt", "w").write(f"STDOUT: {res2.stdout}\nSTDERR: {res2.stderr}")
    assert torture_task not in unproven


def test_stale_writer_cannot_overwrite(tmp_path):
    import sys
    sys.path.append(str(Path(__file__).parent.parent.resolve()))
    import scripts.agent_handoff_ledger as ledger
    
    ledger_path = setup_ledger(
        tmp_path,
        unproven_edges=["A"],
        blocker="NONE",
        proven_edges=[],
    )
    
    # 1. Reader 1 reads the ledger
    bundle1 = ledger.load_bundle(Path(ledger_path))
    
    # 2. Reader 2 reads the ledger (same revision)
    bundle2 = ledger.load_bundle(Path(ledger_path))
    
    # 3. Reader 1 writes a new state
    ledger.update(Path(ledger_path), bundle1["revision"], {"STATUS": "UPDATED_BY_1"}, "test-writer-1", 5.0)
    
    # 4. Reader 2 tries to write with the stale revision
    try:
        ledger.update(Path(ledger_path), bundle2["revision"], {"STATUS": "UPDATED_BY_2"}, "test-writer-2", 5.0)
        assert False, "Expected LedgerError due to revision conflict"
    except ledger.LedgerError as e:
        assert "revision conflict" in str(e)
    
    # Verify that the state was not overwritten
    bundle_final = ledger.load_bundle(Path(ledger_path))
    assert bundle_final["record"]["STATUS"] == "UPDATED_BY_1"
