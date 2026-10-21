"""Tests for CP-38 / CQ-38 / GB-ROLLBACK-BOUNDARY-01: Rollback Boundary Engine & Safe Fallback Isolation.

Verifies:
1. Feature flag toggling downgrades mode from TURBO to SAFE_BASELINE.
2. Disabling flags does not retroactively delete committed external effects.
3. Queue remains completely readable and intact during and after fallback.
4. V1 settings, single-instance worker, and CTRL+A/C/V hotkeys remain untouched.
5. Evidence generated with ['release-diff', 'feature-flags', 'compatibility-tests'].
"""

import pytest

from courier_core.rollback_boundary_engine import (
    FeatureFlagState,
    OperatingMode,
    RollbackBoundaryEngine,
)


def test_feature_flag_toggling_switches_mode_to_safe_baseline():
    """Triggering fallback immediately restores SAFE_BASELINE operating mode."""
    flags = FeatureFlagState(enable_turbo=True, enable_ui_v2=True)
    engine = RollbackBoundaryEngine(flags=flags)
    assert engine.current_mode == OperatingMode.TURBO_ENABLED

    rec = engine.trigger_immediate_fallback(
        incident_id="inc-turbo-throttle",
        incident_reason="Provider rate-limiting observed in secondary worker",
    )

    assert rec.prior_mode == OperatingMode.TURBO_ENABLED
    assert rec.current_mode == OperatingMode.SAFE_BASELINE
    assert engine.current_mode == OperatingMode.SAFE_BASELINE
    assert engine.flags.enable_turbo is False
    assert engine.flags.enable_ui_v2 is False


def test_external_effects_are_not_retroactively_erased():
    """Committed external mutations are preserved in receipt history after fallback."""
    flags = FeatureFlagState(enable_turbo=True)
    engine = RollbackBoundaryEngine(flags=flags)

    engine.record_external_effect(
        task_id="task-01",
        effect_type="FILE_WRITE",
        effect_receipt="receipt-sha256-abc",
    )
    engine.record_external_effect(
        task_id="task-02",
        effect_type="GIT_COMMIT",
        effect_receipt="commit-sha1-xyz",
    )

    rec = engine.trigger_immediate_fallback("inc-02", "Fallback requested")

    assert rec.retained_external_effects_count == 2
    assert len(engine.external_effect_receipts) == 2
    assert engine.external_effect_receipts[0]["effect_receipt"] == "receipt-sha256-abc"


def test_queue_remains_completely_readable_after_fallback():
    """Enqueued tasks remain 100% readable without loss or corruption across fallback."""
    engine = RollbackBoundaryEngine(FeatureFlagState(enable_turbo=True))

    for i in range(5):
        engine.enqueue_task(f"t-{i}", f"payload content {i}")

    rec = engine.trigger_immediate_fallback("inc-queue", "Fallback validation")

    assert rec.queue_readable_count == 5
    assert len(engine.queue) == 5
    for i, item in enumerate(engine.queue):
        assert item["task_id"] == f"t-{i}"
        assert item["payload"] == f"payload content {i}"


def test_v1_and_ctrl_settings_remain_untouched():
    """V1 terminal settings and hotkeys (CTRL+A/C/V) remain strictly untouched."""
    engine = RollbackBoundaryEngine()
    rec = engine.trigger_immediate_fallback("inc-v1", "Verify V1 invariants")

    assert rec.v1_invariants_untouched is True
    assert engine.flags.v1_terminal_keys_frozen is True


def test_evidence_generation():
    """Emits required evidence with release-diff, feature-flags, and compatibility-tests."""
    engine = RollbackBoundaryEngine(FeatureFlagState(enable_turbo=True))
    engine.enqueue_task("task-e", "payload-e")
    engine.record_external_effect("task-e", "MUTATION", "rcpt-1")
    engine.trigger_immediate_fallback("inc-evid", "Testing evidence output")

    evidence = engine.generate_rollback_evidence()
    required_keys = ["release-diff", "feature-flags", "compatibility-tests"]
    for k in required_keys:
        assert k in evidence

    assert evidence["release-diff"]["target_mode"] == "SAFE_BASELINE"
    assert evidence["compatibility-tests"]["queue_readable"] is True
    assert evidence["compatibility-tests"]["external_effects_retained_not_retroactively_erased"] is True
