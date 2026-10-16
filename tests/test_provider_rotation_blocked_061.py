"""Deterministic offline tests for Seed 061 / Catalog 0666: Provider-Rotation blockieren.

Validates that autonomous provider/account rotation is blocked fail-closed:
- Fallback to an authorized, cross-family provider is allowed (positive case).
- Rotation to another account in the same provider family is blocked (negative case).
- Rotation to unauthorized, unverified, or out-of-scope providers is blocked (negative cases).
- Quota exhaustion without an authorized cross-family fallback enters WAITING_PROVIDER / fail-closed.
"""
import unittest
from unittest.mock import patch

from scripts.provider_circuit import ProviderCircuitBreaker, ProviderState
from scripts.provider_survival import (
    AuthorizedProviderRouter,
    CourierScheduler,
    Provider,
    TaskContext,
    WorkState,
)


class TestProviderRotationBlocked061(unittest.TestCase):
    """Test suite for Seed 061: Provider-Rotation blockieren."""

    def setUp(self):
        self.breaker = ProviderCircuitBreaker(isolated=True)
        self.primary_provider = Provider(
            id="codex-primary",
            is_authorized=True,
            capabilities=["completion"],
            family="codex",
            authority_scopes=("repo",),
        )
        self.task = TaskContext(
            task_id="task-061",
            required_capability="completion",
            authority_scope="repo",
        )

    def test_positive_authorized_cross_family_fallback_allowed(self):
        """Positivfall: Authorized cross-family provider is permitted when primary is down."""
        cross_family_fallback = Provider(
            id="gemini-authorized",
            is_authorized=True,
            capabilities=["completion"],
            family="gemini",
            authority_scopes=("repo",),
        )
        providers = [self.primary_provider, cross_family_fallback]
        router = AuthorizedProviderRouter(self.breaker, lambda: providers)

        # Primary circuit is tripped (e.g. 429 quota exhausted)
        self.breaker.record_failure(
            "codex-primary", "completion", 429, "quota exhausted"
        )
        self.assertTrue(self.breaker.is_open("codex-primary", "completion"))

        fallback = router.find_fallback("codex-primary", self.task)
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback.id, "gemini-authorized")
        self.assertEqual(fallback.family, "gemini")

    def test_negative_same_family_account_rotation_blocked_fail_closed(self):
        """Synthetischer Negativfall: Rotating to a second account in the same family is blocked."""
        same_family_rotated_account = Provider(
            id="codex-secondary-account",
            is_authorized=True,
            capabilities=["completion"],
            family="codex",  # same family -> account rotation attempt
            authority_scopes=("repo",),
        )
        providers = [self.primary_provider, same_family_rotated_account]
        router = AuthorizedProviderRouter(self.breaker, lambda: providers)

        # Primary circuit tripped
        self.breaker.record_failure(
            "codex-primary", "completion", 429, "rate limit or quota"
        )
        self.assertTrue(self.breaker.is_open("codex-primary", "completion"))

        fallback = router.find_fallback("codex-primary", self.task)
        # MUST return None: Account rotation is forbidden
        self.assertIsNone(fallback)

    def test_negative_unauthorized_provider_rotation_blocked(self):
        """Negativfall: Unverified or unauthorized provider cannot be rotated to."""
        unauthorized_provider = Provider(
            id="unauthorized-external-provider",
            is_authorized=False,  # not verified / authorized
            capabilities=["completion"],
            family="external",
            authority_scopes=("repo",),
        )
        providers = [self.primary_provider, unauthorized_provider]
        router = AuthorizedProviderRouter(self.breaker, lambda: providers)

        self.breaker.record_failure(
            "codex-primary", "completion", 429, "quota exhausted"
        )
        fallback = router.find_fallback("codex-primary", self.task)
        self.assertIsNone(fallback)

    def test_negative_out_of_scope_provider_rotation_blocked(self):
        """Negativfall: Provider without required authority scope is blocked."""
        out_of_scope_provider = Provider(
            id="restricted-scope-provider",
            is_authorized=True,
            capabilities=["completion"],
            family="other-family",
            authority_scopes=("sandbox-only",),  # lacks "repo"
        )
        providers = [self.primary_provider, out_of_scope_provider]
        router = AuthorizedProviderRouter(self.breaker, lambda: providers)

        self.breaker.record_failure(
            "codex-primary", "completion", 429, "quota exhausted"
        )
        fallback = router.find_fallback("codex-primary", self.task)
        self.assertIsNone(fallback)

    def test_scheduler_fail_closed_on_rotation_attempt(self):
        """End-to-End Fail-Closed: Scheduler parks task and avoids side-effects on rotation attempt."""
        same_family_rotated_account = Provider(
            id="codex-alt-account",
            is_authorized=True,
            capabilities=["completion"],
            family="codex",
            authority_scopes=("repo",),
        )
        providers = [self.primary_provider, same_family_rotated_account]
        sched = CourierScheduler(
            primary_provider="codex-primary",
            providers=providers,
        )

        # Trip primary circuit
        sched.breaker.record_failure(
            "codex-primary", "completion", 429, "quota exhausted"
        )

        state = sched.evaluate_task_state(self.task)
        # Must evaluate to WAITING_PROVIDER, NOT PROVIDER_READY
        self.assertEqual(state, WorkState.WAITING_PROVIDER)

        # Attempting execution must not dispatch to any rotated provider
        with patch("subprocess.Popen", side_effect=AssertionError("No external subprocesses allowed")):
            sched.execute_with_provider(self.task, "codex-primary")

        self.assertEqual(sched.provider_calls, [])
        self.assertNotIn("task-061", sched.completed_tasks)


if __name__ == "__main__":
    unittest.main()
