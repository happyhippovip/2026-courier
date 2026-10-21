"""Contract tests for CP-17 / P17: Worker Connection Contract, Runtime Identity & Execution Readiness.

Acceptance Criteria:
1. OPEN_AVAILABLE, CONNECTED und arbeitsfähig (EXECUTION_CAPABLE) bleiben strikt getrennt.
2. Ein offenes Fenster/UI ohne authentifizierte Session ist OPEN_AVAILABLE und nicht arbeitsfähig.
3. Fehlender oder unvollständiger Adapter ist CAPABILITY_MISSING und kein Fake-PASS.
4. Fehlende Adapter-Readiness oder fehlende Capability sperrt Ausführung fail-closed.
5. Volle Erfüllung aller drei Dimensionen (Surface + Connection + Adapter) beweist Arbeitsfähigkeit.
"""

import time
import pytest

from courier_core.worker_connection_contract import (
    WorkerState,
    CapabilityMissingError,
    SurfaceIdentity,
    RuntimeIdentity,
    AdapterContract,
    WorkerReadinessReport,
    WorkerVerificationEngine,
)


def test_open_surface_without_authenticated_session_is_open_available_not_connected():
    """CP-17 Acceptance: Ein offenes Fenster/UI ohne authentifizierte Session ist OPEN_AVAILABLE."""
    surface = SurfaceIdentity(
        surface_id="surf-chrome-01",
        window_title="Provider Web UI - Google Chrome",
        pid=12345,
        create_time=time.time() - 100,
        is_visible=True,
    )

    report = WorkerVerificationEngine.evaluate_readiness(
        worker_id="chrome-worker",
        surface=surface,
        connection=None,  # No authenticated Hub connection
        adapter=None,
        requested_capability="browser_execution",
    )

    assert report.state == WorkerState.OPEN_AVAILABLE
    assert report.can_execute is False
    assert "no authenticated Hub connection" in report.reason

    with pytest.raises(CapabilityMissingError) as exc_info:
        WorkerVerificationEngine.enforce_no_fake_pass(report)
    assert "Fake-PASS is strictly prohibited" in str(exc_info.value)


def test_authenticated_worker_without_adapter_is_capability_missing():
    """CP-17 Acceptance: CONNECTED ohne Adapter ist CAPABILITY_MISSING und kein Fake-PASS."""
    identity = RuntimeIdentity.create(
        worker_id="win-node-01",
        session_id="sess-abc-123",
        pid=5555,
        create_time=time.time() - 200,
        host="WIN-HOST-01",
        platform="windows",
        token="secret-auth-token-42",
    )

    report = WorkerVerificationEngine.evaluate_readiness(
        worker_id="win-node-01",
        connection=identity,
        adapter=None,  # Missing execution adapter
        requested_capability="python_test",
    )

    assert report.state == WorkerState.CAPABILITY_MISSING
    assert report.can_execute is False
    assert "has no execution adapter registered (CAPABILITY_MISSING)" in report.reason

    with pytest.raises(CapabilityMissingError):
        WorkerVerificationEngine.enforce_no_fake_pass(report)


def test_adapter_missing_declared_capability_is_capability_missing():
    """CP-17 Acceptance: Adapter ohne die geforderte Fähigkeit ist CAPABILITY_MISSING."""
    identity = RuntimeIdentity.create(
        worker_id="win-node-02",
        session_id="sess-def-456",
        pid=5556,
        create_time=time.time() - 50,
        host="WIN-HOST-02",
        platform="windows",
        token="token-valid",
    )
    # Adapter supports python and powershell, but NOT docker
    adapter = AdapterContract(
        adapter_name="native_script_adapter",
        supported_interface="run_task_v1",
        supported_capabilities=["python", "powershell"],
        effect_classes={"python": "idempotent", "powershell": "non_idempotent"},
    )

    report = WorkerVerificationEngine.evaluate_readiness(
        worker_id="win-node-02",
        connection=identity,
        adapter=adapter,
        requested_capability="docker",
    )

    assert report.state == WorkerState.CAPABILITY_MISSING
    assert report.can_execute is False
    assert "does not declare capability 'docker'" in report.reason


def test_adapter_failing_readiness_probe_is_capability_missing():
    """CP-17 Acceptance: Adapter, dessen Probe fehlschlägt, ist CAPABILITY_MISSING."""
    identity = RuntimeIdentity.create(
        worker_id="win-node-03",
        session_id="sess-ghi-789",
        pid=5557,
        create_time=time.time() - 30,
        host="WIN-HOST-03",
        platform="windows",
        token="token-valid-3",
    )

    # Readiness probe simulates a broken toolchain
    adapter = AdapterContract(
        adapter_name="broken_toolchain_adapter",
        supported_interface="run_task_v1",
        supported_capabilities=["rust_build"],
        is_ready_probe=lambda: False,  # probe fails
    )

    report = WorkerVerificationEngine.evaluate_readiness(
        worker_id="win-node-03",
        connection=identity,
        adapter=adapter,
        requested_capability="rust_build",
    )

    assert report.state == WorkerState.CAPABILITY_MISSING
    assert report.can_execute is False
    assert "failed local readiness probe" in report.reason


def test_full_contract_satisfaction_is_execution_capable():
    """CP-17 Acceptance: Vollständige Erfüllung beweist echte Arbeitsfähigkeit (EXECUTION_CAPABLE)."""
    surface = SurfaceIdentity(
        surface_id="surf-terminal-01",
        window_title="Courier Worker Console",
        pid=9000,
        create_time=time.time() - 500,
        is_visible=True,
    )
    identity = RuntimeIdentity.create(
        worker_id="win-verified-worker",
        session_id="sess-live-999",
        pid=9000,
        create_time=time.time() - 500,
        host="WIN-PRIMARY-01",
        platform="windows",
        token="secure-token-999",
    )
    adapter = AdapterContract(
        adapter_name="powershell_adapter",
        supported_interface="run_task_v1",
        supported_capabilities=["powershell", "python"],
        is_ready_probe=lambda: True,
    )

    report = WorkerVerificationEngine.evaluate_readiness(
        worker_id="win-verified-worker",
        surface=surface,
        connection=identity,
        adapter=adapter,
        requested_capability="powershell",
    )

    assert report.state == WorkerState.EXECUTION_CAPABLE
    assert report.can_execute is True
    assert "Worker has verified runtime identity and adapter implements the requested capability" in report.reason

    # Must NOT raise
    WorkerVerificationEngine.enforce_no_fake_pass(report)


def test_expired_heartbeat_transitions_to_disconnected():
    """CP-17 Acceptance: Abgelaufener Heartbeat führt zu DISCONNECTED."""
    stale_identity = RuntimeIdentity(
        worker_id="stale-worker",
        session_id="sess-stale",
        pid=1111,
        create_time=time.time() - 1000,
        host="HOST-1",
        platform="linux",
        auth_fingerprint="abc",
        last_heartbeat=time.time() - 600,  # 600 seconds ago
    )

    report = WorkerVerificationEngine.evaluate_readiness(
        worker_id="stale-worker",
        connection=stale_identity,
        adapter=None,
        heartbeat_ttl_s=300.0,
    )

    assert report.state == WorkerState.DISCONNECTED
    assert report.can_execute is False
    assert "heartbeat has expired" in report.reason
