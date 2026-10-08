import datetime
import pytest
from scripts.provider_circuit import (
    CircuitState,
    ErrorCategory,
    ProviderCircuitBreaker,
    ProviderState,
)

def test_classify_error_matrix():
    state = CircuitState()
    # 429 variants
    assert state.classify_error(429, "subscription quota exhausted") == ErrorCategory.QUOTA_EXHAUSTED
    assert state.classify_error(429, "usage limit reached") == ErrorCategory.QUOTA_EXHAUSTED
    assert state.classify_error(429, "rate limit exceeded") == ErrorCategory.RATE_LIMITED
    # Auth errors
    assert state.classify_error(401, "unauthorized") == ErrorCategory.AUTH_ERROR
    assert state.classify_error(403, "forbidden") == ErrorCategory.AUTH_ERROR
    # Server / Unavailable
    assert state.classify_error(500, "internal server error") == ErrorCategory.UNAVAILABLE
    assert state.classify_error(503, "service unavailable") == ErrorCategory.UNAVAILABLE
    # String error code and None message resilience
    assert state.classify_error("429", "quota limit") == ErrorCategory.QUOTA_EXHAUSTED
    assert state.classify_error("429", None) == ErrorCategory.RATE_LIMITED
    assert state.classify_error(400, None) == ErrorCategory.UNKNOWN
    # Quota keyword in non-429 message
    assert state.classify_error(200, "out of quota") == ErrorCategory.QUOTA_EXHAUSTED

def test_record_failure_and_state_transitions():
    state = CircuitState()
    assert state.check_circuit() is False

    # Degraded
    state.record_failure(400, "bad request")
    assert state.state == ProviderState.DEGRADED
    assert state.check_circuit() is False

    # Rate limited with future reset
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    state.record_failure(429, "rate limit", reset_time=future)
    assert state.state == ProviderState.RATE_LIMITED
    assert state.check_circuit() is True

    # Quota exhausted
    state.record_failure(429, "quota exhausted", reset_time=future)
    assert state.state == ProviderState.QUOTA_EXHAUSTED
    assert state.check_circuit() is True

    # Auth required (blocks requests regardless of reset)
    state.record_failure(401, "bad token")
    assert state.state == ProviderState.AUTH_REQUIRED
    assert state.check_circuit() is True

    # Unavailable
    state.record_failure(503, "down")
    assert state.state == ProviderState.PROVIDER_UNAVAILABLE
    assert state.check_circuit() is True

def test_reset_time_expiry_transitions_to_recovery_probe():
    state = CircuitState()
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
    state.record_failure(429, "quota", reset_time=past)
    assert state.state == ProviderState.QUOTA_EXHAUSTED
    # Check circuit triggers transition
    assert state.check_circuit() is False
    assert state.state == ProviderState.RECOVERY_PROBE_DUE

def test_naive_timestamp_awareness():
    naive = datetime.datetime(2026, 10, 8, 12, 0, 0)
    aware = CircuitState._as_aware(naive)
    assert aware.tzinfo == datetime.timezone.utc
    assert CircuitState._as_aware(None) is None

def test_claim_probe_single_bounded():
    state = CircuitState()
    state.state = ProviderState.RECOVERY_PROBE_DUE
    assert state.probe_in_flight is False

    # First claim succeeds
    assert state.claim_probe() is True
    assert state.probe_in_flight is True

    # Second concurrent claim rejected
    assert state.claim_probe() is False

    # Success resets everything
    state.record_success()
    assert state.state == ProviderState.AVAILABLE
    assert state.reset_time is None
    assert state.probe_in_flight is False

    # Probe cannot be claimed when AVAILABLE
    assert state.claim_probe() is False

def test_serialization_roundtrip_and_malformed_resilience():
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
    original = CircuitState(
        state=ProviderState.RATE_LIMITED,
        reset_time=future,
        probe_in_flight=True,
    )
    d = original.to_dict()
    assert d["state"] == "RATE_LIMITED"
    assert d["probe_in_flight"] is True
    assert d["reset_time"] == future.isoformat()

    restored = CircuitState.from_dict(d)
    assert restored.state == original.state
    assert restored.probe_in_flight == original.probe_in_flight
    assert restored.reset_time == original.reset_time

    # ISO with 'Z' support
    z_dict = {"state": "QUOTA_EXHAUSTED", "reset_time": "2026-10-08T12:00:00Z", "probe_in_flight": False}
    z_restored = CircuitState.from_dict(z_dict)
    assert z_restored.reset_time.tzinfo == datetime.timezone.utc

    # Malformed reset_time falls back cleanly
    bad_dict = {"state": "AVAILABLE", "reset_time": "not-a-date", "probe_in_flight": False}
    bad_restored = CircuitState.from_dict(bad_dict)
    assert bad_restored.reset_time is None

def test_provider_circuit_breaker_shared_restore_synchronization():
    b1 = ProviderCircuitBreaker(isolated=False)
    b2 = ProviderCircuitBreaker(isolated=False)

    payload = {
        "muse|completion": {
            "state": "QUOTA_EXHAUSTED",
            "reset_time": "2026-10-08T15:00:00+00:00",
            "probe_in_flight": False,
        }
    }
    b1.restore(payload)

    # b2 must observe the restored circuit state via shared reference
    assert b2.is_open("muse", "completion") is True
    circuit = b2.get_circuit("muse", "completion")
    assert circuit.state == ProviderState.QUOTA_EXHAUSTED

    # Success on b2 updates b1
    b2.record_success("muse", "completion")
    assert b1.is_open("muse", "completion") is False
    assert b1.get_circuit("muse", "completion").state == ProviderState.AVAILABLE

def test_provider_circuit_breaker_isolated_mode():
    b_shared = ProviderCircuitBreaker(isolated=False)
    b_isolated = ProviderCircuitBreaker(isolated=True)

    b_isolated.record_failure("codex", "edit", 429, "rate limited")
    assert b_isolated.is_open("codex", "edit") is True
    # Shared breaker remains unaffected
    assert b_shared.is_open("codex", "edit") is False
