import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from courier_worker.service import ControllerClient

def test_l13_worker_drops_payload_on_transport_ambiguity(monkeypatch):
    """
    PROVE: If the worker's /start call fails due to a transient network error,
    it correctly proceeds. But when it delivers the result, the controller rejects
    it with 409 not_started. The worker mistakenly treats this 409 as "stale"
    and permanently deletes the result from its durable outbox.
    """
    client = ControllerClient("http://localhost", token="x")

    def mock_call(self, method, path, payload=None):
        # Simulate the Controller returning 409 not_started
        return 409, {"code": "not_started", "message": "report /v1/start before a result"}

    monkeypatch.setattr(ControllerClient, "_call", mock_call)
    
    # Red test: The worker incorrectly returns "stale" which causes outbox_remove!
    assert client.deliver({"dispatch_id": "d1", "result_id": "r1"}) == "stale"

