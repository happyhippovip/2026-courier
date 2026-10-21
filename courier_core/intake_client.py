"""Client-side idempotent intake submitter with retry and conflict handling (CP-06 / GB-INTAKE-01).

Ensures that intake requests can be reliably submitted across lossy networks.
If a request is sent and the response is lost, retries with the same idempotency key
cleanly return the acknowledged goal receipt without creating duplicate goals.
Contradictory payloads for the same idempotency key are rejected fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


class IntakeClientError(Exception):
    """Base exception for intake submission errors."""


class IdempotencyConflictError(IntakeClientError):
    """Raised when server detects conflicting payload for the same idempotency key."""


class IntakeRejectedError(IntakeClientError):
    """Raised when server permanently rejects submission with 4xx."""


@dataclass(frozen=True)
class GoalReceipt:
    goal_id: str
    status: str
    duplicate: bool
    attempts: int


def compute_idempotency_key(payload: dict) -> str:
    """Generate a stable idempotency key from canonical goal payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"idem-goal-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


def submit_goal_with_retry(
    http_post_fn: Callable[..., Any],
    goal_payload: dict,
    *,
    idempotency_key: Optional[str] = None,
    headers: Optional[dict] = None,
    max_attempts: int = 3,
    backoff_s: float = 0.05,
    endpoint: str = "/goals",
) -> GoalReceipt:
    """Submit a goal with idempotency key and retry on transient communication failures.

    Args:
        http_post_fn: Callable taking (url, headers=..., json=...) and returning response object.
        goal_payload: Dict containing goal_text and optional workflow_plan/budget.
        idempotency_key: Client-provided idempotency key or derived from payload.
        headers: Optional auth headers.
        max_attempts: Number of delivery attempts before giving up.
        backoff_s: Sleep between attempts.
        endpoint: URL path for goals API.

    Returns:
        GoalReceipt with confirmed goal_id, status, duplicate flag, and attempt count.

    Raises:
        IdempotencyConflictError: If server responds HTTP 409 (conflicting payload).
        IntakeRejectedError: If server returns non-retryable 4xx client error.
        IntakeClientError: If all retry attempts fail due to network/server errors.
    """
    key = idempotency_key or compute_idempotency_key(goal_payload)
    body = dict(goal_payload)
    body["idempotency_key"] = key

    req_headers = dict(headers or {})
    req_headers["Idempotency-Key"] = key

    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = http_post_fn(endpoint, headers=req_headers, json=body)
            # Support both Flask test client responses and requests.Response
            status_code = getattr(resp, "status_code", None)
            get_json_fn = getattr(resp, "get_json", None)
            if callable(get_json_fn):
                resp_data = get_json_fn() or {}
            elif callable(getattr(resp, "json", None)):
                resp_data = resp.json() or {}
            else:
                resp_data = {}

            if status_code in (200, 201):
                return GoalReceipt(
                    goal_id=resp_data.get("goal_id", ""),
                    status=resp_data.get("status", "ACTIVE"),
                    duplicate=bool(resp_data.get("duplicate", False)),
                    attempts=attempt,
                )
            elif status_code == 409:
                err_msg = resp_data.get("message") or resp_data.get("error") or "idempotency_conflict"
                raise IdempotencyConflictError(f"HTTP 409: {err_msg}")
            elif status_code and 400 <= status_code < 500:
                err_msg = resp_data.get("error") or f"HTTP {status_code}"
                raise IntakeRejectedError(f"HTTP {status_code}: {err_msg}")
            else:
                last_error = IntakeClientError(f"Server error HTTP {status_code}: {resp_data}")
        except (IdempotencyConflictError, IntakeRejectedError):
            raise
        except Exception as exc:
            last_error = exc

        if attempt < max_attempts and backoff_s > 0:
            time.sleep(backoff_s)

    raise IntakeClientError(f"Failed to submit goal after {max_attempts} attempts: {last_error}")
