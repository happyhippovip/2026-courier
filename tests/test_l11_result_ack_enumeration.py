import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from courier_worker.service import ControllerClient, ControllerError

def test_l11_worker_accepts_only_enumerated_canonical_acks(monkeypatch):
    """
    PROVE: The worker blindly trusts any HTTP 200 as a valid delivery,
    even if the canonical enumerated ACK is missing.
    """
    client = ControllerClient("http://localhost", token="x")

    def mock_call_factory(status, body):
        def fake_call(self, method, path, payload=None):
            return status, body
        return fake_call

    # 1. Valid Canonical ACKs
    monkeypatch.setattr(ControllerClient, "_call", mock_call_factory(200, {"status": "ACCEPTED_FOR_VERIFY"}))
    assert client.deliver({}) == "accepted"

    monkeypatch.setattr(ControllerClient, "_call", mock_call_factory(200, {"status": "ACK_DUPLICATE"}))
    assert client.deliver({}) == "accepted"

    # 2. Flaw: Blindly accepts an empty 200 (or unknown body structure)!
    monkeypatch.setattr(ControllerClient, "_call", mock_call_factory(200, None))
    # Red Test: Prove the flawed state (it returns 'accepted' instead of raising)
    assert client.deliver({}) == "accepted"
    
    # And it even accepts garbage JSON statuses!
    monkeypatch.setattr(ControllerClient, "_call", mock_call_factory(200, {"status": "SOMETHING_ELSE"}))
    assert client.deliver({}) == "accepted"

