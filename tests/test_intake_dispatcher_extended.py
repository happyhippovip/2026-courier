import pytest
import time
from scripts.intake_dispatcher import (
    _parse_created_at,
    resolve_execution_ref,
    UNBOUND_EXECUTION_REF,
    INTAKE_DISPATCH_GRACE_SECONDS,
    ADMISSION_DISPATCHING,
    ADMISSION_ADMITTED,
)

def test_constants():
    assert UNBOUND_EXECUTION_REF == "DISPATCHED_UNBOUND"
    assert INTAKE_DISPATCH_GRACE_SECONDS == 300
    assert ADMISSION_DISPATCHING == "DISPATCHING"
    assert ADMISSION_ADMITTED == "ADMITTED"

def test_parse_created_at_formats():
    assert _parse_created_at("2026-10-08T12:00:00Z") is not None
    assert _parse_created_at("2026-10-08T12:00:00+00:00") is not None
    assert _parse_created_at("invalid-date") is None
    assert _parse_created_at(None) is None
    assert _parse_created_at(12345) is None

def test_resolve_execution_ref_ambiguous_returns_none(monkeypatch):
    # If multiple candidate runs created after since_epoch, fail closed (return None)
    now = time.time()
    fake_runs = [
        {"databaseId": 101, "createdAt": "2026-10-08T15:00:00Z"},
        {"databaseId": 102, "createdAt": "2026-10-08T15:00:01Z"}
    ]
    
    class FakeProc:
        stdout = f'[{{"databaseId": 101, "createdAt": "2030-01-01T00:00:00Z"}}, {{"databaseId": 102, "createdAt": "2030-01-01T00:00:01Z"}}]'
        returncode = 0
        
    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
    assert resolve_execution_ref("dispatch.yml", since_epoch=1000, attempts=1) is None
