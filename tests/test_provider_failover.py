import json
import pytest
from courier_core.provider_failover import (
    ProviderCandidate,
    ProviderFailoverRouter,
    RoutingResult,
    CircuitBreakerState,
)


def test_primary_provider_success():
    router = ProviderFailoverRouter(autonomous_spend_limit_eur=0.0)

    p1 = ProviderCandidate(
        provider_id="mock-primary",
        cost_estimate_eur=0.0,
        handler=lambda: "primary-success",
    )
    p2 = ProviderCandidate(
        provider_id="mock-fallback",
        cost_estimate_eur=0.0,
        handler=lambda: "fallback-success",
    )

    result = router.execute_with_failover([p1, p2])
    assert result.success is True
    assert result.chosen_provider == "mock-primary"
    assert result.output == "primary-success"
    assert len(result.attempts) == 1
    assert result.attempts[0]["status"] == "SUCCESS"


def test_cost_gate_blocks_paid_primary_and_selects_free_fallback():
    router = ProviderFailoverRouter(autonomous_spend_limit_eur=0.0)

    paid_primary = ProviderCandidate(
        provider_id="gemini-paid",
        cost_estimate_eur=0.05,
        handler=lambda: "should-not-run",
    )
    free_fallback = ProviderCandidate(
        provider_id="local-model",
        cost_estimate_eur=0.0,
        handler=lambda: "local-success",
    )

    result = router.execute_with_failover([paid_primary, free_fallback])
    assert result.success is True
    assert result.chosen_provider == "local-model"
    assert result.output == "local-success"
    assert len(result.attempts) == 2
    assert result.attempts[0]["status"] == "COST_GATE_BLOCKED"
    assert result.attempts[1]["status"] == "SUCCESS"


def test_transient_failure_falls_back_to_secondary():
    router = ProviderFailoverRouter(autonomous_spend_limit_eur=0.0)

    def failing_handler():
        raise RuntimeError("Rate limit 429")

    p1 = ProviderCandidate(
        provider_id="cloud-free",
        cost_estimate_eur=0.0,
        handler=failing_handler,
    )
    p2 = ProviderCandidate(
        provider_id="deterministic-mock",
        cost_estimate_eur=0.0,
        handler=lambda: "mock-result",
    )

    result = router.execute_with_failover([p1, p2])
    assert result.success is True
    assert result.chosen_provider == "deterministic-mock"
    assert result.output == "mock-result"
    assert len(result.attempts) == 2
    assert result.attempts[0]["status"] == "FAILED"
    assert "Rate limit 429" in result.attempts[0]["error"]
    assert result.attempts[1]["status"] == "SUCCESS"


def test_all_providers_exhausted_fail_closed():
    router = ProviderFailoverRouter(autonomous_spend_limit_eur=0.0)

    p1 = ProviderCandidate(
        provider_id="prov-1",
        cost_estimate_eur=0.0,
        handler=lambda: (_ for _ in ()).throw(ValueError("Timeout")),
    )
    p2 = ProviderCandidate(
        provider_id="prov-2",
        cost_estimate_eur=1.0,  # paid
        handler=lambda: "paid",
    )

    result = router.execute_with_failover([p1, p2])
    assert result.success is False
    assert result.chosen_provider is None
    assert result.error == "ALL_PROVIDERS_EXHAUSTED_OR_BLOCKED"
    assert len(result.attempts) == 2


def test_non_idempotent_failure_halts_failover():
    router = ProviderFailoverRouter(autonomous_spend_limit_eur=0.0)
    calls = []

    def side_effect_timeout():
        calls.append("p1")
        raise TimeoutError("Timed out after mutating external state")

    def fallback_handler():
        calls.append("p2")
        return "duplicate-mutation"

    p1 = ProviderCandidate(provider_id="prov-1", cost_estimate_eur=0.0, handler=side_effect_timeout)
    p2 = ProviderCandidate(provider_id="prov-2", cost_estimate_eur=0.0, handler=fallback_handler)

    result = router.execute_with_failover([p1, p2], idempotent=False)
    assert result.success is False
    assert result.error == "NON_IDEMPOTENT_HANDLER_FAILED_NO_FAILOVER"
    assert calls == ["p1"]


def test_circuit_breaker_tripping_and_cooldown():
    router = ProviderFailoverRouter(
        autonomous_spend_limit_eur=0.0,
        failure_threshold=2,
        cooldown_seconds=10.0,
    )

    def fail_call():
        raise ConnectionError("Service unavailable")

    p1 = ProviderCandidate(provider_id="flaky-service", cost_estimate_eur=0.0, handler=fail_call)
    p2 = ProviderCandidate(provider_id="backup-mock", cost_estimate_eur=0.0, handler=lambda: "ok")

    # Call 1: failure 1
    r1 = router.execute_with_failover([p1, p2])
    assert r1.success is True
    assert router.get_circuit_state("flaky-service") == CircuitBreakerState.CLOSED

    # Call 2: failure 2 -> reaches threshold 2 -> circuit trips to OPEN
    r2 = router.execute_with_failover([p1, p2])
    assert r2.success is True
    assert router.get_circuit_state("flaky-service") == CircuitBreakerState.OPEN

    # Call 3: p1 is skipped immediately due to circuit OPEN
    r3 = router.execute_with_failover([p1, p2])
    assert r3.success is True
    assert r3.attempts[0]["status"] == "CIRCUIT_OPEN_SKIPPED"


def test_cli_invocation(tmp_path):
    import subprocess
    import sys
    import os
    from pathlib import Path

    manifest_file = tmp_path / "candidates.json"
    manifest_file.write_text(
        json.dumps({
            "candidates": [
                {"provider_id": "paid-1", "cost_estimate_eur": 0.50},
                {"provider_id": "free-mock", "cost_estimate_eur": 0.0}
            ]
        }),
        encoding="utf-8"
    )

    cmd = [
        sys.executable,
        "-m",
        "courier_core.provider_failover",
        "select",
        "--candidates",
        str(manifest_file),
        "--spend-limit",
        "0.0",
    ]
    root = str(Path(__file__).resolve().parent.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = root
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=root, env=env)
    out = json.loads(proc.stdout)
    assert out["selected_provider"] == "free-mock"
    assert out["status"] == "SELECTED"
