import datetime
from scripts.provider_circuit import (
    CircuitState,
    ErrorCategory,
    ProviderCircuitBreaker,
    ProviderState,
)


def test_classify_error_categories():
    cs = CircuitState()
    assert cs.classify_error(429, "rate limit exceeded") == ErrorCategory.RATE_LIMITED
    assert cs.classify_error(429, "quota exhausted for day") == ErrorCategory.QUOTA_EXHAUSTED
    assert cs.classify_error(401, "unauthorized") == ErrorCategory.AUTH_ERROR
    assert cs.classify_error(403, "forbidden") == ErrorCategory.AUTH_ERROR
    assert cs.classify_error(503, "service unavailable") == ErrorCategory.UNAVAILABLE
    assert cs.classify_error(400, "bad request") == ErrorCategory.UNKNOWN


def test_naive_timestamp_awareness():
    naive_dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
    aware = CircuitState._as_aware(naive_dt)
    assert aware.tzinfo == datetime.timezone.utc
    assert CircuitState._as_aware(None) is None


def test_rate_limit_and_probe_transition():
    cs = CircuitState()
    future_reset = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
    cs.record_failure(429, "rate limit exceeded", reset_time=future_reset)

    assert cs.state == ProviderState.RATE_LIMITED
    assert cs.check_circuit() is True  # Blocked

    # When reset time is in the past
    past_reset = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)
    cs.record_failure(429, "rate limit exceeded", reset_time=past_reset)
    assert cs.check_circuit() is False  # Transitions to RECOVERY_PROBE_DUE
    assert cs.state == ProviderState.RECOVERY_PROBE_DUE

    # Single probe claim
    assert cs.claim_probe() is True
    assert cs.claim_probe() is False  # Duplicate probe blocked

    # Success restores to AVAILABLE
    cs.record_success()
    assert cs.state == ProviderState.AVAILABLE
    assert cs.check_circuit() is False


def test_auth_error_requires_user_and_never_probes():
    cs = CircuitState()
    cs.record_failure(401, "invalid credentials")
    assert cs.state == ProviderState.AUTH_REQUIRED
    assert cs.check_circuit() is True
    assert cs.claim_probe() is False


def test_serialization_roundtrip():
    cs = CircuitState(
        state=ProviderState.RATE_LIMITED,
        reset_time=datetime.datetime(2026, 5, 1, 10, 0, 0, tzinfo=datetime.timezone.utc),
        probe_in_flight=False,
    )
    d = cs.to_dict()
    restored = CircuitState.from_dict(d)
    assert restored.state == ProviderState.RATE_LIMITED
    assert restored.reset_time == cs.reset_time
    assert restored.probe_in_flight is False


def test_circuit_breaker_isolation_and_restore():
    cb1 = ProviderCircuitBreaker(isolated=True)
    cb2 = ProviderCircuitBreaker(isolated=True)

    cb1.record_failure("gemini", "chat", 429, "quota reached")
    assert cb1.is_open("gemini", "chat") is True
    assert cb2.is_open("gemini", "chat") is False  # Isolated

    dump = cb1.to_dict()
    cb2.restore(dump)
    assert cb2.is_open("gemini", "chat") is True
