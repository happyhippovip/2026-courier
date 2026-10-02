import pytest
import os
import json
from scripts.queue_processor import process_queue

def test_process_queue_does_not_abort_entire_session_on_single_failure(tmp_path):
    """
    Ensures that a partial queue batch failure does NOT cause the session to retire
    or abort early. If 3 items exist and item 1 fails, items 2 and 3 must still process,
    proving the queue tail is consumed and the physical session doesn't prematurely die.
    """
    os.makedirs("intakes/pending", exist_ok=True)
    os.makedirs("intakes/processed", exist_ok=True)
    
    # Write 3 items
    for i in range(3):
        with open(f"intakes/pending/item_{i}.json", "w") as f:
            if i == 1:
                f.write("{malformed") # Will cause json.load to fail in already_recorded()
            else:
                json.dump({"intent": "test", "id": i}, f)
                
    # process_queue should handle all 3, moving 0 and 2, but failing on 1
    # without sys.exit
    
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
        # Cleanup
        for i in range(3):
            if os.path.exists(f"intakes/pending/item_{i}.json"):
                os.remove(f"intakes/pending/item_{i}.json")
            if os.path.exists(f"intakes/processed/item_{i}.json"):
                os.remove(f"intakes/processed/item_{i}.json")


def test_queue_tail_durability_preserves_all_attributes():
    """
    Explicitly verify the architecture preserves:
    QUEUED_ITEM_ID, ORDER, LANE, SOURCE, PRECONDITION, STATUS
    and that session destruction would not be the only durable representation.
    """
    import os
    import json
    from scripts.intake_dispatcher import save_central_state, load_central_state

    state_file = "test_tail_durability_state.json"
    if os.path.exists(state_file):
        os.remove(state_file)

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
    
    # Clean up
    if os.path.exists(state_file):
        os.remove(state_file)

