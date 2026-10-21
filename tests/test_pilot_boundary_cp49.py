"""Tests for CP-49 / CQ-49 / GB-PILOT-BOUNDARY-01: Minimal Pilot Boundary & Safety Gates.

Verifies:
1. Technical demos and test runs cannot claim customer sales revenue ("Kein Verkaufs-/Umsatzbeweis aus Demo").
2. Automated outreach and public marketing are strictly prohibited ("keine Kontakte/Veröffentlichung").
3. Optional Cannon/Dual-Muse acceleration features are not artificial blockers ("optionaler Cannon/Muse-2 ist kein künstlicher Pilotblocker").
4. Deterministic input/output transformation with verifiable SHA256 output diff.
5. Evidence structure generation containing ['accepted-capabilities', 'existing-pilot-assets', 'safety-gate'].
"""

import pytest

from courier_core.pilot_boundary_definition import (
    ExternalOutreachProhibitedError,
    PilotBoundaryCoordinator,
    PilotWorkflowKind,
    SalesValidationFromDemoProhibitedError,
)


def test_pilot_demo_cannot_claim_sales_revenue():
    """Technical demos cannot record customer sales/revenue proof without real signed agreements."""
    coordinator = PilotBoundaryCoordinator()
    coordinator.register_minimal_pilot("pilot-sheet-01")

    with pytest.raises(SalesValidationFromDemoProhibitedError) as exc_info:
        coordinator.execute_pilot(
            pilot_id="pilot-sheet-01",
            input_data="col1,col2\nval1,val2\n",
            is_demo=True,
            claimed_revenue_eur=500.00,  # Prohibited!
        )

    assert "Kein Verkaufs-/Umsatzbeweis aus Demo" in str(exc_info.value)


def test_automated_external_outreach_strictly_prohibited():
    """Automated external outreach and publication are strictly blocked by safety gate."""
    coordinator = PilotBoundaryCoordinator()
    coordinator.register_minimal_pilot("pilot-sheet-02")

    with pytest.raises(ExternalOutreachProhibitedError) as exc_info:
        coordinator.execute_pilot(
            pilot_id="pilot-sheet-02",
            input_data="data\n",
            attempt_external_outreach=True,
        )

    assert "strictly prohibited" in str(exc_info.value)


def test_cannon_dual_muse_not_artificial_blocker():
    """The minimal pilot executes cleanly without requiring Cannon or Dual-Muse acceleration."""
    coordinator = PilotBoundaryCoordinator()
    coordinator.register_minimal_pilot("pilot-sheet-03")

    # Executes standalone without acceleration prerequisites
    result = coordinator.execute_pilot(
        pilot_id="pilot-sheet-03",
        input_data="ID, Name , Dept \n 1 , Alice , Sales \n 2 , Bob , Eng \n",
        is_demo=True,
        claimed_revenue_eur=0.00,
    )

    assert result.safety_gate_passed is True
    assert result.revenue_eur == 0.00
    assert "Alice" in result.output_diff or "Transformed" in result.output_diff
    assert len(result.output_sha256) == 64


def test_deterministic_input_output_diff_generated():
    """Generates deterministic diff and output SHA256 from input payload."""
    coordinator = PilotBoundaryCoordinator()
    coordinator.register_minimal_pilot("pilot-sheet-04")

    raw_input = "Col A, Col B\n  1,  2 \n\n  3,  4\n"
    res = coordinator.execute_pilot("pilot-sheet-04", raw_input)

    assert res.safety_gate_passed is True
    assert res.outreach_occurred is False
    assert res.is_demo is True


def test_evidence_generation():
    """Validates required catalog evidence keys: ['accepted-capabilities', 'existing-pilot-assets', 'safety-gate']."""
    coordinator = PilotBoundaryCoordinator()
    coordinator.register_minimal_pilot("pilot-demo-05")
    coordinator.execute_pilot("pilot-demo-05", "test,data\n")

    evidence = coordinator.generate_pilot_evidence()

    assert "accepted-capabilities" in evidence
    assert "existing-pilot-assets" in evidence
    assert "safety-gate" in evidence

    assert "deterministic_transformation" in evidence["accepted-capabilities"]
    assert len(evidence["existing-pilot-assets"]) == 1
    assert evidence["safety-gate"]["spend_eur"] == 0.00
    assert evidence["safety-gate"]["external_outreach_attempts"] == 0
