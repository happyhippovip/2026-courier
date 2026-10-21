"""Failure Taxonomy, Circuit Breaker & Retry Policy Engine (CP-19 / CQ-19 / GB-CIRCUIT-01)

Durable Worker Contract:
1. Strict separation of:
   - Provider Disruption (500, 502, 503, 504, network breaks) -> Transient, bounded retries, trips circuit breaker
   - Rate Limit (429, quota exhaustion) -> Bounded backoff using Retry-After, NO account switching to evade limits
   - Auth Failure (401, 403, revoked/expired token) -> Non-retryable, blind retries forbidden, human gate required
   - Task Malformed (400, schema mismatch, context length) -> Non-retryable, provider circuit unaffected, task rejected
2. Zero Account Switching to Evade Limits:
   - Attempting account rotation to bypass quotas is strictly prohibited.
3. Response Fixtures:
   - Deterministic fixtures for standard provider HTTP/RPC response payloads.
4. Required Evidence:
   - error-mapping, retry-policy, provider-surface.
"""

from __future__ import annotations

import datetime
import json
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FailureCategory(str, Enum):
    AUTH_FAILURE = "AUTH_FAILURE"
    TASK_MALFORMED = "TASK_MALFORMED"
    RATE_LIMIT = "RATE_LIMIT"
    PROVIDER_DISRUPTION = "PROVIDER_DISRUPTION"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class CircuitAction(str, Enum):
    NO_IMPACT = "NO_IMPACT"
    AUTH_GATE_REQUIRED = "AUTH_GATE_REQUIRED"
    ENTER_RATE_LIMIT_COOLDOWN = "ENTER_RATE_LIMIT_COOLDOWN"
    RECORD_DISRUPTION_FAILURE = "RECORD_DISRUPTION_FAILURE"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_REQUIRED = "AUTH_REQUIRED"


class AccountSwitchingForbiddenError(RuntimeError):
    """Raised when an execution or retry path attempts to rotate/switch accounts to bypass limits."""


class BlindRetryForbiddenError(RuntimeError):
    """Raised when an unapproved blind retry is attempted on non-retryable failures (401/403/400)."""


@dataclass(frozen=True)
class ClassifiedFailure:
    category: FailureCategory
    status_code: Optional[int]
    error_message: str
    retryable: bool
    circuit_action: CircuitAction
    retry_after_seconds: Optional[float] = None
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "retryable": self.retryable,
            "circuit_action": self.circuit_action.value,
            "retry_after_seconds": self.retry_after_seconds,
            "recommended_action": self.recommended_action,
        }


@dataclass(frozen=True)
class RetryDecision:
    allow_retry: bool
    category: FailureCategory
    wait_seconds: float
    reason: str
    attempt_number: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow_retry": self.allow_retry,
            "category": self.category.value,
            "wait_seconds": self.wait_seconds,
            "reason": self.reason,
            "attempt_number": self.attempt_number,
        }


# Standard Response Fixtures
RESPONSE_FIXTURES: Dict[str, Dict[str, Any]] = {
    "401_UNAUTHORIZED": {
        "status_code": 401,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "error": {
                "code": 401,
                "status": "UNAUTHENTICATED",
                "message": "Invalid API key provided or auth token expired",
            }
        }),
    },
    "403_FORBIDDEN": {
        "status_code": 403,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "error": {
                "code": 403,
                "status": "PERMISSION_DENIED",
                "message": "The caller does not have permission to execute specified model",
            }
        }),
    },
    "400_BAD_REQUEST_SCHEMA": {
        "status_code": 400,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "Schema validation failed: 'prompt' parameter cannot be empty",
            }
        }),
    },
    "400_PROMPT_TOO_LONG": {
        "status_code": 400,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "Context window exceeded: 135000 tokens exceeds model limit of 32768",
            }
        }),
    },
    "429_RATE_LIMIT_WITH_RETRY_AFTER": {
        "status_code": 429,
        "headers": {
            "Content-Type": "application/json",
            "Retry-After": "30",
        },
        "body": json.dumps({
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "Rate limit exceeded: Concurrency ceiling reached for current tier",
            }
        }),
    },
    "429_QUOTA_EXHAUSTED": {
        "status_code": 429,
        "headers": {
            "Content-Type": "application/json",
            "Retry-After": "120",
        },
        "body": json.dumps({
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "Quota limit reached for today. Reset at midnight UTC",
            }
        }),
    },
    "500_INTERNAL_SERVER_ERROR": {
        "status_code": 500,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "error": {
                "code": 500,
                "status": "INTERNAL",
                "message": "Internal error encountered while dispatching generation backend",
            }
        }),
    },
    "503_SERVICE_UNAVAILABLE": {
        "status_code": 503,
        "headers": {
            "Content-Type": "application/json",
            "Retry-After": "15",
        },
        "body": json.dumps({
            "error": {
                "code": 503,
                "status": "UNAVAILABLE",
                "message": "Inference backend overloaded. Please retry later",
            }
        }),
    },
}


def parse_retry_after(headers: Optional[Dict[str, str]] = None) -> Optional[float]:
    """Extract and parse numeric retry-after seconds from response headers."""
    if not headers:
        return None
    for key, value in headers.items():
        if key.lower() in ("retry-after", "x-retry-after", "retry-after-ms"):
            try:
                val = float(value.strip())
                if key.lower() == "retry-after-ms":
                    return max(0.0, val / 1000.0)
                return max(0.0, val)
            except (ValueError, TypeError):
                continue
    return None


def classify_failure(
    status_code: Optional[int] = None,
    error_message: str = "",
    headers: Optional[Dict[str, str]] = None,
) -> ClassifiedFailure:
    """Classifies an error payload into standard failure categories.

    Strict rules:
    - 401/403 -> AUTH_FAILURE (never blind retry, circuit action = AUTH_GATE_REQUIRED)
    - 400 -> TASK_MALFORMED (never blind retry, circuit action = NO_IMPACT)
    - 429 -> RATE_LIMIT (retryable after wait, circuit action = ENTER_RATE_LIMIT_COOLDOWN)
    - 500/502/503/504 -> PROVIDER_DISRUPTION (bounded retry, circuit action = RECORD_DISRUPTION_FAILURE)
    """
    msg = error_message.lower()
    retry_after = parse_retry_after(headers)

    # 1. Auth failure
    if status_code in (401, 403) or any(k in msg for k in ("unauthorized", "unauthenticated", "permission_denied", "forbidden", "invalid api key", "token expired")):
        return ClassifiedFailure(
            category=FailureCategory.AUTH_FAILURE,
            status_code=status_code,
            error_message=error_message,
            retryable=False,
            circuit_action=CircuitAction.AUTH_GATE_REQUIRED,
            retry_after_seconds=None,
            recommended_action="HALT_FOR_HUMAN_AUTH_GATE: Do not retry automatically; credential refresh or permission grant required.",
        )

    # 2. Task Malformed / Bad Request
    if status_code == 400 or any(k in msg for k in ("invalid_argument", "schema validation failed", "context window exceeded", "prompt cannot be empty", "bad request", "syntax error")):
        return ClassifiedFailure(
            category=FailureCategory.TASK_MALFORMED,
            status_code=status_code,
            error_message=error_message,
            retryable=False,
            circuit_action=CircuitAction.NO_IMPACT,
            retry_after_seconds=None,
            recommended_action="REJECT_TASK_MALFORMED: Provider is healthy; reject the defective task with an error receipt.",
        )

    # 3. Rate Limit / Quota Exhaustion
    if status_code == 429 or any(k in msg for k in ("resource_exhausted", "rate limit exceeded", "too many requests", "quota limit reached", "quota_exhausted")):
        return ClassifiedFailure(
            category=FailureCategory.RATE_LIMIT,
            status_code=status_code,
            error_message=error_message,
            retryable=True,
            circuit_action=CircuitAction.ENTER_RATE_LIMIT_COOLDOWN,
            retry_after_seconds=retry_after,
            recommended_action="RATE_LIMIT_BACKOFF: Wait for cooldown window; account switching to evade limits is strictly blocked.",
        )

    # 4. Provider Disruption / Transient Infrastructure Error
    if status_code in (500, 502, 503, 504) or any(k in msg for k in ("internal error", "unavailable", "bad gateway", "gateway timeout", "connection refused", "connection reset", "broken pipe")):
        return ClassifiedFailure(
            category=FailureCategory.PROVIDER_DISRUPTION,
            status_code=status_code,
            error_message=error_message,
            retryable=True,
            circuit_action=CircuitAction.RECORD_DISRUPTION_FAILURE,
            retry_after_seconds=retry_after,
            recommended_action="BOUNDED_DISRUPTION_RETRY: Exponential backoff with disruption counter tracking; trip circuit on repeat failures.",
        )

    # 5. Unknown / Unclassified Failure
    return ClassifiedFailure(
        category=FailureCategory.UNKNOWN_ERROR,
        status_code=status_code,
        error_message=error_message,
        retryable=False,
        circuit_action=CircuitAction.NO_IMPACT,
        retry_after_seconds=None,
        recommended_action="FAIL_CLOSED_INVESTIGATE: Unclassified error; fail closed without speculative retry.",
    )


class TaxonomyCircuitBreaker:
    """Circuit Breaker that observes Failure Taxonomy to protect healthy providers from bad tasks."""

    def __init__(
        self,
        failure_threshold: int = 3,
        disruption_cooldown_seconds: float = 30.0,
        rate_limit_cooldown_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.disruption_cooldown_seconds = disruption_cooldown_seconds
        self.rate_limit_cooldown_seconds = rate_limit_cooldown_seconds

        self.state: CircuitState = CircuitState.CLOSED
        self.disruption_failures: int = 0
        self.last_failure_time: float = 0.0
        self.cooldown_until: float = 0.0
        self.probe_in_flight: bool = False

    def can_attempt(self, now: Optional[float] = None) -> bool:
        current_time = time.time() if now is None else now

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.AUTH_REQUIRED:
            # Requires explicit manual or configured re-auth; never clears by timer alone
            return False

        if self.state in (CircuitState.OPEN, CircuitState.RATE_LIMITED):
            if current_time >= self.cooldown_until:
                self.state = CircuitState.HALF_OPEN
                self.probe_in_flight = False
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            if not self.probe_in_flight:
                self.probe_in_flight = True
                return True
            return False

        return False

    def record_classified_failure(
        self,
        failure: ClassifiedFailure,
        now: Optional[float] = None,
    ) -> None:
        current_time = time.time() if now is None else now
        self.last_failure_time = current_time

        if failure.circuit_action == CircuitAction.NO_IMPACT:
            # Bad task does NOT increment disruption counter or change state
            return

        if failure.circuit_action == CircuitAction.AUTH_GATE_REQUIRED:
            self.state = CircuitState.AUTH_REQUIRED
            self.probe_in_flight = False
            return

        if failure.circuit_action == CircuitAction.ENTER_RATE_LIMIT_COOLDOWN:
            self.state = CircuitState.RATE_LIMITED
            cooldown = failure.retry_after_seconds if failure.retry_after_seconds is not None else self.rate_limit_cooldown_seconds
            self.cooldown_until = current_time + cooldown
            self.probe_in_flight = False
            return

        if failure.circuit_action == CircuitAction.RECORD_DISRUPTION_FAILURE:
            self.disruption_failures += 1
            if self.disruption_failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                cooldown = failure.retry_after_seconds if failure.retry_after_seconds is not None else self.disruption_cooldown_seconds
                self.cooldown_until = current_time + cooldown
            self.probe_in_flight = False

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED
        self.disruption_failures = 0
        self.probe_in_flight = False
        self.cooldown_until = 0.0

    def restore_auth(self) -> None:
        """Called when authenticated credentials have been updated/verified by an approved human gate."""
        if self.state == CircuitState.AUTH_REQUIRED:
            self.state = CircuitState.CLOSED
            self.disruption_failures = 0
            self.probe_in_flight = False


class TaxonomyRetryPolicy:
    """Evaluates retry feasibility and enforces strict policy boundaries."""

    def __init__(
        self,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds

    def evaluate(
        self,
        failure: ClassifiedFailure,
        attempt_number: int,
        allow_account_switch: bool = False,
    ) -> RetryDecision:
        # INVARIANT: Zero Account Switching to Evade Limits
        if allow_account_switch:
            raise AccountSwitchingForbiddenError(
                "Policy violation: Switching or rotating accounts to evade provider rate limits or quotas is strictly forbidden."
            )

        # INVARIANT: Non-retryable failures are never blindly repeated
        if not failure.retryable:
            return RetryDecision(
                allow_retry=False,
                category=failure.category,
                wait_seconds=0.0,
                reason=f"Non-retryable failure ({failure.category.value}): blind retry is strictly prohibited.",
                attempt_number=attempt_number,
            )

        # INVARIANT: Bounded retry limit
        if attempt_number >= self.max_retries:
            return RetryDecision(
                allow_retry=False,
                category=failure.category,
                wait_seconds=0.0,
                reason=f"Max retry limit ({self.max_retries}) exhausted.",
                attempt_number=attempt_number,
            )

        # Rate Limit Backoff using Retry-After
        if failure.category == FailureCategory.RATE_LIMIT:
            wait_time = failure.retry_after_seconds if failure.retry_after_seconds is not None else self.base_backoff_seconds * (2 ** attempt_number)
            wait_time = min(self.max_backoff_seconds, max(0.0, wait_time))
            return RetryDecision(
                allow_retry=True,
                category=failure.category,
                wait_seconds=wait_time,
                reason="Rate-limit backoff wait: respecting Retry-After without limit evasion.",
                attempt_number=attempt_number,
            )

        # Provider Disruption Backoff
        if failure.category == FailureCategory.PROVIDER_DISRUPTION:
            backoff = self.base_backoff_seconds * (2 ** attempt_number)
            wait_time = min(self.max_backoff_seconds, max(0.0, backoff))
            return RetryDecision(
                allow_retry=True,
                category=failure.category,
                wait_seconds=wait_time,
                reason="Transient provider disruption: bounded exponential backoff.",
                attempt_number=attempt_number,
            )

        # Default fallback: fail-closed
        return RetryDecision(
            allow_retry=False,
            category=failure.category,
            wait_seconds=0.0,
            reason=f"Default fail-closed for category {failure.category.value}",
            attempt_number=attempt_number,
        )


def generate_failure_taxonomy_evidence() -> Dict[str, Any]:
    """Generates CP-19 required evidence: ['error-mapping', 'retry-policy', 'provider-surface']."""
    policy = TaxonomyRetryPolicy(max_retries=3)
    cb = TaxonomyCircuitBreaker(failure_threshold=3)

    tested_fixtures: List[Dict[str, Any]] = []

    for name, fix in RESPONSE_FIXTURES.items():
        classified = classify_failure(
            status_code=fix.get("status_code"),
            error_message=fix.get("body", ""),
            headers=fix.get("headers"),
        )
        decision = policy.evaluate(classified, attempt_number=1)
        cb.record_classified_failure(classified)

        tested_fixtures.append({
            "fixture_name": name,
            "status_code": fix.get("status_code"),
            "category": classified.category.value,
            "retryable": classified.retryable,
            "circuit_action": classified.circuit_action.value,
            "allow_retry_attempt_1": decision.allow_retry,
            "wait_seconds": decision.wait_seconds,
            "circuit_state_after": cb.state.value,
        })

    error_mapping = [
        {
            "status_code": 401,
            "category": FailureCategory.AUTH_FAILURE.value,
            "retryable": False,
            "circuit_action": CircuitAction.AUTH_GATE_REQUIRED.value,
            "rationale": "Credentials invalid/expired; blind retry causes account lockout.",
        },
        {
            "status_code": 403,
            "category": FailureCategory.AUTH_FAILURE.value,
            "retryable": False,
            "circuit_action": CircuitAction.AUTH_GATE_REQUIRED.value,
            "rationale": "Permission denied; human gate required to adjust authorization.",
        },
        {
            "status_code": 400,
            "category": FailureCategory.TASK_MALFORMED.value,
            "retryable": False,
            "circuit_action": CircuitAction.NO_IMPACT.value,
            "rationale": "Malformed task parameters/schema; provider is healthy, task rejected.",
        },
        {
            "status_code": 429,
            "category": FailureCategory.RATE_LIMIT.value,
            "retryable": True,
            "circuit_action": CircuitAction.ENTER_RATE_LIMIT_COOLDOWN.value,
            "rationale": "Quota/rate throttled; wait for Retry-After, account switching blocked.",
        },
        {
            "status_code": 500,
            "category": FailureCategory.PROVIDER_DISRUPTION.value,
            "retryable": True,
            "circuit_action": CircuitAction.RECORD_DISRUPTION_FAILURE.value,
            "rationale": "Internal backend error; bounded retry and trips circuit if persistent.",
        },
        {
            "status_code": 503,
            "category": FailureCategory.PROVIDER_DISRUPTION.value,
            "retryable": True,
            "circuit_action": CircuitAction.RECORD_DISRUPTION_FAILURE.value,
            "rationale": "Service temporarily unavailable; retry with backoff.",
        },
    ]

    retry_policy_spec = {
        "max_retries": 3,
        "base_backoff_seconds": 1.0,
        "max_backoff_seconds": 60.0,
        "account_switching_allowed": False,
        "blind_retry_allowed_for_401_403": False,
        "blind_retry_allowed_for_400": False,
        "retry_after_enforcement": "Respected strictly as sleep/cooldown duration; no busy-polling",
    }

    return {
        "required_evidence": ["error-mapping", "retry-policy", "provider-surface"],
        "error-mapping": error_mapping,
        "retry-policy": retry_policy_spec,
        "provider-surface": {
            "tested_fixtures_count": len(tested_fixtures),
            "fixtures": tested_fixtures,
        },
    }
