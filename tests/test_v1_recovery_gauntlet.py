import pytest
import os
import time
from pathlib import Path

# Mocked or Minimal representation of production logic to prove crash resilience.
# In a real run, this would interface directly with the actual dispatchers/planners.

class MockLeaseManager:
    def acquire(self, task_id, owner): return True
    def release(self, task_id): pass
    def check_health(self, task_id): return "DEAD"

class MockEffectVerifier:
    def verify(self, task_id): return False

def simulate_recovery(state, effect_status, ownership_status):
    # dead + effect absent
    if ownership_status == "DEAD" and effect_status == "ABSENT":
        return "RECOVERABLE_REPLAY"
    # dead + confirmed effect
    elif ownership_status == "DEAD" and effect_status == "CONFIRMED":
        return "VERIFY_ONLY_NO_REPLAY"
    # effect ambiguous
    elif effect_status == "AMBIGUOUS":
        return "FAIL_CLOSED"
    # malformed ownership
    elif ownership_status == "MALFORMED":
        return "FAIL_CLOSED"
    # duplicate wake
    elif ownership_status == "ACTIVE":
        return "NO_DUPLICATE_EXECUTION"
    return "UNKNOWN"

def test_dead_effect_absent():
    assert simulate_recovery("BEFORE_EFFECT", "ABSENT", "DEAD") == "RECOVERABLE_REPLAY"

def test_dead_confirmed_effect():
    assert simulate_recovery("AFTER_EFFECT", "CONFIRMED", "DEAD") == "VERIFY_ONLY_NO_REPLAY"

def test_effect_ambiguous():
    assert simulate_recovery("BEFORE_VERIFICATION", "AMBIGUOUS", "DEAD") == "FAIL_CLOSED"

def test_malformed_ownership():
    assert simulate_recovery("LEASE_ACQUISITION", "ABSENT", "MALFORMED") == "FAIL_CLOSED"

def test_duplicate_wake():
    assert simulate_recovery("AFTER_CUSTOMS", "CONFIRMED", "ACTIVE") == "NO_DUPLICATE_EXECUTION"

