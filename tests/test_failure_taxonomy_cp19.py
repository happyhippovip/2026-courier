"""Tests for CP-19 / CQ-19 / GB-CIRCUIT-01: Failure Taxonomy, Circuit Breaker & Retry Policy

Verifies:
1. 401/403 or invalid requests are not blindly repeated.
2. 400 (malformed task) does not affect or trip the provider circuit breaker.
3. 429 Rate-limit respects Retry-After solely as wait information without account switching to evade limits.
4. Provider disruptions (500, 503) trigger bounded retries and trip the circuit breaker on threshold.
5. Evidence generation produces ['error-mapping', 'retry-policy', 'provider-surface'].
"""

import json
import pytest

from courier_core.failure_taxonomy import (
    AccountSwitchingForbiddenError,
    CircuitAction,
    CircuitState,
    ClassifiedFailure,
    FailureCategory,
    RESPONSE_FIXTURES,
    TaxonomyCircuitBreaker,
    TaxonomyRetryPolicy,
    classify_failure,
    generate_failure_taxonomy_evidence,
    parse_retry_after,
)


def test_401_403_auth_failure_is_not_blindly_retried():
    policy = TaxonomyRetryPolicy(max_retries=3)
    cb = TaxonomyCircuitBreaker(failure_threshold=3)

    for fix_name in ("401_UNAUTHORIZED", "403_FORBIDDEN"):
        fix = RESPONSE_FIXTURES[fix_name]
        classified = classify_failure(
            status_code=fix["status_code"],
            error_message=fix["body"],
            headers=fix["headers"],
        )

        assert classified.category == FailureCategory.AUTH_FAILURE
        assert classified.retryable is False
        assert classified.circuit_action == CircuitAction.AUTH_GATE_REQUIRED

        # Evaluate retry decision
        decision = policy.evaluate(classified, attempt_number=1)
        assert decision.allow_retry is False
        assert "blind retry is strictly prohibited" in decision.reason

        # Circuit breaker reaction
        cb.record_classified_failure(classified)
        assert cb.state == CircuitState.AUTH_REQUIRED
        assert cb.can_attempt() is False

    # Operator re-auth resets the gate
    cb.restore_auth()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_attempt() is True


def test_400_task_malformed_rejects_task_without_affecting_provider_circuit():
    policy = TaxonomyRetryPolicy(max_retries=3)
    cb = TaxonomyCircuitBreaker(failure_threshold=3)

    for fix_name in ("400_BAD_REQUEST_SCHEMA", "400_PROMPT_TOO_LONG"):
        fix = RESPONSE_FIXTURES[fix_name]
        classified = classify_failure(
            status_code=fix["status_code"],
            error_message=fix["body"],
            headers=fix["headers"],
        )

        assert classified.category == FailureCategory.TASK_MALFORMED
        assert classified.retryable is False
        assert classified.circuit_action == CircuitAction.NO_IMPACT

        decision = policy.evaluate(classified, attempt_number=1)
        assert decision.allow_retry is False

        # Fire 10 consecutive malformed task errors on the circuit breaker
        for _ in range(10):
            cb.record_classified_failure(classified)

        # Provider MUST NOT be penalized or tripped
        assert cb.state == CircuitState.CLOSED
        assert cb.disruption_failures == 0
        assert cb.can_attempt() is True


def test_429_rate_limit_respects_retry_after_and_forbids_account_switching():
    policy = TaxonomyRetryPolicy(max_retries=3)
    cb = TaxonomyCircuitBreaker(failure_threshold=3, rate_limit_cooldown_seconds=30.0)

    fix = RESPONSE_FIXTURES["429_RATE_LIMIT_WITH_RETRY_AFTER"]
    classified = classify_failure(
        status_code=fix["status_code"],
        error_message=fix["body"],
        headers=fix["headers"],
    )

    assert classified.category == FailureCategory.RATE_LIMIT
    assert classified.retryable is True
    assert classified.retry_after_seconds == 30.0
    assert classified.circuit_action == CircuitAction.ENTER_RATE_LIMIT_COOLDOWN

    # Retry decision respects wait window
    decision = policy.evaluate(classified, attempt_number=1)
    assert decision.allow_retry is True
    assert decision.wait_seconds == 30.0

    # Policy invariant: Account switching to evade rate limit is strictly forbidden
    with pytest.raises(AccountSwitchingForbiddenError, match="Policy violation: Switching or rotating accounts"):
        policy.evaluate(classified, attempt_number=1, allow_account_switch=True)

    # Circuit breaker enters RATE_LIMITED cooldown
    start_time = 1000.0
    cb.record_classified_failure(classified, now=start_time)
    assert cb.state == CircuitState.RATE_LIMITED
    assert cb.cooldown_until == start_time + 30.0
    assert cb.can_attempt(now=start_time + 10.0) is False
    assert cb.can_attempt(now=start_time + 31.0) is True  # Transition to HALF_OPEN probe


def test_provider_disruption_500_503_bounded_retries_and_trips_circuit():
    policy = TaxonomyRetryPolicy(max_retries=3, base_backoff_seconds=1.0)
    cb = TaxonomyCircuitBreaker(failure_threshold=3, disruption_cooldown_seconds=45.0)

    fix = RESPONSE_FIXTURES["500_INTERNAL_SERVER_ERROR"]
    classified = classify_failure(
        status_code=fix["status_code"],
        error_message=fix["body"],
        headers=fix["headers"],
    )

    assert classified.category == FailureCategory.PROVIDER_DISRUPTION
    assert classified.retryable is True
    assert classified.circuit_action == CircuitAction.RECORD_DISRUPTION_FAILURE

    # Attempts 1 and 2 allow retry with exponential backoff
    d1 = policy.evaluate(classified, attempt_number=1)
    assert d1.allow_retry is True
    assert d1.wait_seconds == 2.0  # 1.0 * (2 ** 1)

    d2 = policy.evaluate(classified, attempt_number=2)
    assert d2.allow_retry is True
    assert d2.wait_seconds == 4.0  # 1.0 * (2 ** 2)

    # Attempt 3 exceeds max_retries=3 -> halted
    d3 = policy.evaluate(classified, attempt_number=3)
    assert d3.allow_retry is False
    assert "Max retry limit" in d3.reason

    # Circuit breaker threshold test: failures 1 and 2 keep circuit CLOSED
    now = 5000.0
    cb.record_classified_failure(classified, now=now)
    assert cb.state == CircuitState.CLOSED
    assert cb.disruption_failures == 1

    cb.record_classified_failure(classified, now=now)
    assert cb.state == CircuitState.CLOSED
    assert cb.disruption_failures == 2

    # Failure 3 trips circuit to OPEN
    cb.record_classified_failure(classified, now=now)
    assert cb.state == CircuitState.OPEN
    assert cb.disruption_failures == 3
    assert cb.cooldown_until == now + 45.0

    # Blocked during cooldown
    assert cb.can_attempt(now=now + 10.0) is False
    # Allowed probe after cooldown
    assert cb.can_attempt(now=now + 46.0) is True
    assert cb.state == CircuitState.HALF_OPEN

    # Success restores circuit to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.disruption_failures == 0


def test_parse_retry_after_headers():
    assert parse_retry_after({"Retry-After": "15"}) == 15.0
    assert parse_retry_after({"x-retry-after": "42.5"}) == 42.5
    assert parse_retry_after({"retry-after-ms": "5000"}) == 5.0
    assert parse_retry_after({"Other-Header": "abc"}) is None
    assert parse_retry_after(None) is None


def test_response_fixtures_and_evidence_generation():
    evidence = generate_failure_taxonomy_evidence()

    assert evidence["required_evidence"] == ["error-mapping", "retry-policy", "provider-surface"]

    error_mapping = evidence["error-mapping"]
    assert len(error_mapping) >= 6
    status_codes = [e["status_code"] for e in error_mapping]
    assert 401 in status_codes
    assert 403 in status_codes
    assert 400 in status_codes
    assert 429 in status_codes
    assert 500 in status_codes
    assert 503 in status_codes

    retry_policy = evidence["retry-policy"]
    assert retry_policy["max_retries"] == 3
    assert retry_policy["account_switching_allowed"] is False
    assert retry_policy["blind_retry_allowed_for_401_403"] is False
    assert retry_policy["blind_retry_allowed_for_400"] is False

    provider_surface = evidence["provider-surface"]
    assert provider_surface["tested_fixtures_count"] == len(RESPONSE_FIXTURES)
    for fix in provider_surface["fixtures"]:
        assert "fixture_name" in fix
        assert "category" in fix
        assert "circuit_action" in fix
