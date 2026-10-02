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

