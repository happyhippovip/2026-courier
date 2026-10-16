import pytest
import os
import json
from scripts.queue_processor import process_queue

def test_process_queue_does_not_abort_entire_session_on_single_failure(tmp_path, monkeypatch):
    """
    Ensures that a partial queue batch failure does NOT cause the session to retire
    or abort early. If 3 items exist and item 1 fails, items 2 and 3 must still process,
    proving the queue tail is consumed and the physical session doesn't prematurely die.
    """
    monkeypatch.chdir(tmp_path)
    os.makedirs("intakes/pending", exist_ok=True)
    os.makedirs("intakes/processed", exist_ok=True)
    
    # Write 3 items
    for i in range(3):
        with open(f"intakes/pending/item_{i}.json", "w") as f:
            if i == 1:
                f.write("{malformed") # Will cause json.load to fail in already_recorded()
            else:
                json.dump({"intent": "test", "id": i}, f)
                
    # We must patch dispatch_intake so it doesn't actually dispatch
    import scripts.queue_processor as qp
    original_dispatch = qp.dispatch_intake
    
    def mock_dispatch(fpath):
        with open(fpath, "r") as ff:
            data = ff.read()
        if "malformed" in data:
            raise ValueError("Malformed JSON")
        return None
        
    qp.dispatch_intake = mock_dispatch

    try:
        qp.process_queue()
        
        processed = os.listdir("intakes/processed")
        pending = os.listdir("intakes/pending")
        
        # Item 0 and 2 should be in processed
        assert "item_0.json" in processed
        assert "item_2.json" in processed
        
        # Item 1 failed to parse so it stays in pending (or moves to failed if implemented)
        assert "item_1.json" in pending
    finally:
        qp.dispatch_intake = original_dispatch


def test_queue_tail_durability_preserves_all_attributes(tmp_path, monkeypatch):
    """
    Explicitly verify the architecture preserves:
    QUEUED_ITEM_ID, ORDER, LANE, SOURCE, PRECONDITION, STATUS
    and that session destruction would not be the only durable representation.
    """
    monkeypatch.chdir(tmp_path)
    import json
    from scripts.intake_dispatcher import save_central_state, load_central_state

    state_file = "test_tail_durability_state.json"

    # Simulate preserving the queue tail before session retirement
    mock_state = {
        "tasks": {
            "queued_item_2": {
                "queued_item_id": "q-1002",
                "order": 2,
                "lane": "revenue_v1",
                "source": "github_webhook",
                "precondition": "PR_OPEN",
                "status": "PENDING_EXECUTION"
            }
        }
    }
    
    # Save durably (fsync + replace)
    save_central_state(state_file, mock_state)
    
    # Prove the session can be completely destroyed and another session can 
    # reconstruct the exact queued item attributes from disk
    restored_state = load_central_state(state_file)
    restored_task = restored_state["tasks"]["queued_item_2"]
    
    assert restored_task["queued_item_id"] == "q-1002"
    assert restored_task["order"] == 2
    assert restored_task["lane"] == "revenue_v1"
    assert restored_task["source"] == "github_webhook"
    assert restored_task["precondition"] == "PR_OPEN"
    assert restored_task["status"] == "PENDING_EXECUTION"


def test_anti_thrash_duplicate_wake_dedupe(tmp_path, monkeypatch):
    """
    Ensure that identical, repeated wakes/prompts do not spin up new physical
    sessions or re-dispatch if the state has not materially changed (no duplicate).
    """
    monkeypatch.chdir(tmp_path)
    import json
    from scripts.intake_dispatcher import save_central_state, load_central_state, dispatch_intake, fingerprint_task_id

    # Create a mock pending intake
    os.makedirs("intakes/pending", exist_ok=True)
    intake_data = {
        "customer_reference": "ref-dup-1",
        "target_owner": "org",
        "target_repo": "repo",
        "target_sha": "abc1234"
    }
    with open("intakes/pending/dup_item.json", "w") as f:
        json.dump(intake_data, f)
        
    state_file = "central_state.json"
        
    task_id = fingerprint_task_id(intake_data)
    
    # Simulate first admission already happened
    mock_state = {
        "tasks": {
            task_id: {
                "task_id": task_id,
                "admission": "ADMITTED",
                "state": "DISPATCHED_TO_EXTERNAL"
            }
        }
    }
    save_central_state(state_file, mock_state)
    
    # Mock dispatch to prove it isn't called
    called = []
    import scripts.intake_dispatcher as idisp
    original_subprocess = idisp.subprocess.run
    idisp.subprocess.run = lambda *args, **kwargs: called.append(True)
    
    try:
        # Re-dispatching the exact same intake should skip (anti-thrash)
        # We test dispatch_intake returns the task_id but doesn't run subprocess
        res_task = idisp.dispatch_intake("intakes/pending/dup_item.json")
        
        assert res_task == task_id
        assert len(called) == 0, "Duplicate wake triggered a physical execution!"
    finally:
        idisp.subprocess.run = original_subprocess
