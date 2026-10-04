import pytest
from courier_core.controller import WorkerIdentity, ApiError

def test_valid_worker_identities():
    assert WorkerIdentity.parse("worker-123") == "worker-123"
    assert WorkerIdentity.parse("w1") == "w1"
    assert WorkerIdentity.parse("MAC-01") == "MAC-01"

def test_malformed_worker_identities():
    with pytest.raises(ApiError) as exc:
        WorkerIdentity.parse("invalid worker")
    assert exc.value.code == "invalid_worker_id"

    with pytest.raises(ApiError) as exc:
        WorkerIdentity.parse("UNKNOWN")
    assert exc.value.code == "invalid_worker_id"

    with pytest.raises(ApiError) as exc:
        WorkerIdentity.parse("")
    assert exc.value.code == "invalid_worker_id"

