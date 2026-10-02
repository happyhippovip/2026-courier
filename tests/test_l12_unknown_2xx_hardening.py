import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from courier_worker.service import ControllerClient, ControllerError

class MockHttp:
    def __init__(self):
        self.responses = []
        self.calls = []

    def request(self, method, url, body=None, headers=None):
        self.calls.append((method, url, body))
        class MockResp:
            status = self.responses[0][0]
            data = self.responses[0][1]
        self.responses.pop(0)
        return MockResp()

def test_l12_worker_treats_empty_200_as_no_work(monkeypatch):
    """
    PROVE: The worker's claim() method treats an unknown 200 (e.g. from a load balancer)
    as "no work" (returns None) rather than an infrastructure fault.
    """
    http = MockHttp()
    client = ControllerClient("http://localhost", token="x")
    client._conn = lambda: http # wait, _call uses _conn()

    def mock_call_factory(status, body):
        def fake_call(self, method, path, payload=None):
            return status, body
        return fake_call

    # 1. Valid 204 means No Work
    monkeypatch.setattr(ControllerClient, "_call", mock_call_factory(204, None))
    assert client.claim("w1") is None

    # 2. Valid 200 with dictionary means Work Claimed
    monkeypatch.setattr(ControllerClient, "_call", mock_call_factory(200, {"task_id": "abc"}))
    assert client.claim("w1") == {"task_id": "abc"}

    # 3. Flaw: Unknown/empty 200 returns None (treating infrastructure error as "no work")
    monkeypatch.setattr(ControllerClient, "_call", mock_call_factory(200, None))
    
    # Red test: this should raise ControllerError to trigger exponential backoff,
    # but it currently returns None and causes the worker to loop happily.
    assert client.claim("w1") is None
