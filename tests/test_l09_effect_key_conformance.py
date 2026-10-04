import json
import os
import pytest
import hashlib
from pathlib import Path

# Fix sys.path for test
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from courier_core.events import Event, EventType
import adapters.synthetic as synthetic

class DummyTask:
    def __init__(self, effect_key="cfx-111", params=None):
        self.effect_key = effect_key
        self.params = params or {}
        self.effect_class = "non_idempotent"

def ready(payload):
    return Event(
        type=EventType.RESULT_READY,
        task_id="t1",
        attempt=1,
        dispatch_id="d1",
        worker_id="w1",
        result_id="r1",
        payload=payload
    )

def test_l09_verifier_enforces_effect_key_in_evidence(tmp_path):
    """
    PROVE: The verifier must reject evidence if the adapter cannot prove
    it passed the controller's exact effect_key to the provider.
    """
    task = DummyTask(effect_key="cfx-111", params={"write": "out.txt", "content": "golden"})
    
    # Adapter runs but ignores the effect_key (as L08 showed it does today)
    # It writes "golden" to out.txt instead of including the effect_key.
    (tmp_path / "out.txt").write_text("golden")
    digest = hashlib.sha256(b"golden").hexdigest()
    
    payload = {
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": digest}]
    }
    
    verdict = synthetic.verify(task, ready(payload), tmp_path)
    
    # Red test: The verifier currently blindly accepts this, but the provider-idempotency
    # contract requires the effect_key to be strictly present in the accepted evidence.
    assert verdict.accepted is False, "Verifier accepted evidence without effect_key conformance"
