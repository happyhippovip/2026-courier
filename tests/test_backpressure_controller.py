"""Tests for courier_core.backpressure_controller (Dynamic Backpressure Flow Controller)."""

import json
import pytest
from datetime import datetime, timezone
from courier_core.backpressure_controller import (
    BackpressureController,
    FlowState,
    BackpressureDirective,
    PermitExhaustedError,
    BackpressureShedLoadError,
    main,
)


def test_aimd_rate_adaptation(tmp_path):
    store_file = tmp_path / "bp_state.json"
    controller = BackpressureController(
        store_path=str(store_file),
        initial_rate=10.0,
        min_rate=2.0,
        max_rate=50.0,
        additive_step=2.0,
        backoff_factor=0.5,
    )

    assert controller.current_rate == 10.0

    # Healthy feedback: rate increases additively
    controller.report_feedback(latency_ms=50.0, is_error=False)
    assert controller.current_rate == 12.0
    controller.report_feedback(latency_ms=60.0, is_error=False)
    assert controller.current_rate == 14.0

    # Degraded feedback: rate drops multiplicatively
    controller.report_feedback(latency_ms=1500.0, is_error=True)
    assert controller.current_rate == 7.0

    # Repeated degradation does not drop below min_rate
    controller.report_feedback(latency_ms=2000.0, is_error=True)
    controller.report_feedback(latency_ms=2000.0, is_error=True)
    assert controller.current_rate == 2.0


def test_permit_acquisition_and_inflight_capacity(tmp_path):
    controller = BackpressureController(
        store_path=str(tmp_path / "bp.json"),
        initial_rate=10.0,
        max_inflight=3,
    )

    # Acquire permits within capacity
    t1 = controller.acquire_permit(task_id="task-1")
    t2 = controller.acquire_permit(task_id="task-2")
    t3 = controller.acquire_permit(task_id="task-3")
    assert t1 and t2 and t3
    assert controller.inflight_count == 3

    # Attempting to acquire beyond max_inflight raises PermitExhaustedError
    with pytest.raises(PermitExhaustedError):
        controller.acquire_permit(task_id="task-4")

    # Release task-1, freeing capacity
    controller.release_permit(task_id="task-1")
    assert controller.inflight_count == 2

    # Now task-4 can be acquired
    t4 = controller.acquire_permit(task_id="task-4")
    assert t4 is True
    assert controller.inflight_count == 3


def test_load_shedding_under_critical_saturation(tmp_path):
    controller = BackpressureController(
        store_path=str(tmp_path / "bp.json"),
        initial_rate=10.0,
        error_threshold_shed=0.6,
    )

    # Incur burst of errors to trigger SHED_LOAD
    for _ in range(5):
        controller.report_feedback(latency_ms=3000.0, is_error=True)

    directive = controller.get_directive()
    assert directive.state == FlowState.SHED_LOAD

    # Fail-closed rejection
    with pytest.raises(BackpressureShedLoadError):
        controller.acquire_permit(task_id="task-reject")


def test_governor_directive_transitions(tmp_path):
    controller = BackpressureController(
        store_path=str(tmp_path / "bp.json"),
        initial_rate=20.0,
    )

    # Starts in HEALTHY
    assert controller.state == FlowState.HEALTHY

    # Set manual drain or trigger throttled
    controller.set_state(FlowState.THROTTLED, reason="High queue depth")
    assert controller.state == FlowState.THROTTLED
    assert controller.get_directive().state == FlowState.THROTTLED

    controller.set_state(FlowState.DRAINING, reason="Cluster graceful shutdown")
    assert controller.state == FlowState.DRAINING
    assert controller.get_directive().state == FlowState.DRAINING


def test_persistence_and_journal_snapshot(tmp_path):
    store_file = tmp_path / "persisted_bp.json"
    c1 = BackpressureController(store_path=str(store_file), initial_rate=15.0)
    c1.report_feedback(latency_ms=40.0, is_error=False)
    c1.acquire_permit("task-x")
    c1.save()

    # Reopen from disk
    c2 = BackpressureController(store_path=str(store_file))
    assert c2.current_rate == 17.0
    assert "task-x" in c2.active_inflight
    assert c2.inflight_count == 1


def test_cli_backpressure_controller(tmp_path, capsys):
    state_file = tmp_path / "cli_bp.json"

    # Status CLI
    rc1 = main(["--store", str(state_file), "status"])
    assert rc1 == 0
    assert "HEALTHY" in capsys.readouterr().out

    # Acquire CLI
    rc2 = main(["--store", str(state_file), "acquire", "--task-id", "CLI_T1"])
    assert rc2 == 0
    assert "ACQUIRED" in capsys.readouterr().out

    # Release CLI
    rc3 = main(["--store", str(state_file), "release", "--task-id", "CLI_T1"])
    assert rc3 == 0
    assert "RELEASED" in capsys.readouterr().out

    # Feedback CLI
    rc4 = main(["--store", str(state_file), "feedback", "--latency-ms", "150.0", "--error"])
    assert rc4 == 0
    assert "UPDATED" in capsys.readouterr().out
