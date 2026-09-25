import pytest
import os
import sys
import time
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.scope_ledger import ScopeLedger

@pytest.fixture
def ledger(tmp_path):
    db_path = tmp_path / "scopes.sqlite3"
    ledger = ScopeLedger(str(db_path))
    yield ledger

def test_acquire_write_write_conflict(ledger):
    l1 = ledger.acquire_lease("file_x", "WRITE", "t1", "e1", "w1")
    assert l1 is not None
    
    l2 = ledger.acquire_lease("file_x", "WRITE", "t2", "e2", "w2")
    assert l2 is None

def test_acquire_read_write_conflict(ledger):
    l1 = ledger.acquire_lease("/bar", "READ", "t1", "e1", "w1")
    assert l1 is not None
    
    l2 = ledger.acquire_lease("/bar", "WRITE", "t2", "e2", "w2")
    assert l2 is None
    
    l3 = ledger.acquire_lease("/bar", "READ", "t3", "e3", "w3")
    assert l3 is not None

def test_acquire_overlap_conflict(ledger):
    l1 = ledger.acquire_lease("/foo", "WRITE", "t1", "e1", "w1")
    assert l1 is not None
    
    l2 = ledger.acquire_lease("/foo/bar", "WRITE", "t2", "e2", "w2")
    assert l2 is None

def test_fencing_token_expiry(ledger):
    l1 = ledger.acquire_lease("/baz", "WRITE", "t1", "e1", "w1", ttl=0.1)
    assert l1 is not None
    
    assert ledger.verify_fencing_token(l1["fencing_token"]) is True
    
    time.sleep(0.15)
    
    assert ledger.verify_fencing_token(l1["fencing_token"]) is False
    
    l2 = ledger.acquire_lease("/baz", "WRITE", "t2", "e2", "w2")
    assert l2 is not None

def test_reconcile_crashed_worker(ledger):
    l1 = ledger.acquire_lease("/path1", "WRITE", "t1", "e1", "w1", ttl=60)
    l2 = ledger.acquire_lease("/path2", "WRITE", "t2", "e2", "w2", ttl=60)
    
    assert ledger.verify_fencing_token(l1["fencing_token"]) is True
    assert ledger.verify_fencing_token(l2["fencing_token"]) is True
    
    ledger.reconcile_crashed_worker("w1")
    
    assert ledger.verify_fencing_token(l1["fencing_token"]) is False
    assert ledger.verify_fencing_token(l2["fencing_token"]) is True
    
    # W3 can now claim /path1 since W1's lease was artificially expired
    l3 = ledger.acquire_lease("/path1", "WRITE", "t3", "e3", "w3")
    assert l3 is not None

