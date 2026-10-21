"""Tests for CP-50 / CQ-50 / GB-RETROSPECTIVE-SYNTHESIS-01: Retrospective Synthesis & Progress Valuation.

Verifies:
1. Zero percentage values without explicit denominators ("Keine Prozentwerte ohne Nenner").
2. Zero fabricated savings or fictional financial projections ("keine erfundenen Einsparungen").
3. Calendar dates alone never trigger re-audits without code drift ("Kalenderdatum allein löst kein Re-Audit aus").
4. Automatic purchases are strictly prohibited ("kein Automatik-Kauf").
5. Deactivation of redundant tasks and explicit identification of the next primary bottleneck.
6. Evidence structure generation containing ['accepted-results', 'actual-usage', 'known-limitations'].
"""

import pytest

from courier_core.retrospective_synthesis_engine import (
    AutonomousPurchaseProhibitedError,
    FabricatedSavingsProhibitedError,
    MissingDenominatorError,
    RetrospectiveSynthesisEngine,
    TemporalReAuditTriggerProhibitedError,
)


def test_percentage_without_denominator_raises_error():
    """Attempting to emit percentages without a valid denominator raises MissingDenominatorError."""
    engine = RetrospectiveSynthesisEngine()

    with pytest.raises(MissingDenominatorError) as exc_info:
        engine.create_metric_fraction(numerator=45, denominator=None, description="Task Completion")

    assert "Keine Prozentwerte ohne Nenner" in str(exc_info.value)

    with pytest.raises(MissingDenominatorError):
        engine.create_metric_fraction(numerator=45, denominator=0, description="Zero Denominator")


def test_valid_metric_fraction_formats_truthfully():
    """Valid metric fractions display numerator, denominator, and computed percentage."""
    engine = RetrospectiveSynthesisEngine()

    mf = engine.create_metric_fraction(numerator=50, denominator=50, description="All 50 Catalog Units")
    assert mf.percentage == 100.0
    assert "100.0% (50/50)" in mf.formatted


def test_fabricated_savings_strictly_prohibited():
    """Claiming speculative cost savings raises FabricatedSavingsProhibitedError."""
    engine = RetrospectiveSynthesisEngine()

    with pytest.raises(FabricatedSavingsProhibitedError) as exc_info:
        engine.record_cost_metric(actual_incurred_spend_eur=0.00, claimed_savings_eur=10000.0)

    assert "keine erfundenen Einsparungen" in str(exc_info.value)


def test_autonomous_purchase_strictly_prohibited():
    """Attempting autonomous external purchases raises AutonomousPurchaseProhibitedError."""
    engine = RetrospectiveSynthesisEngine()

    with pytest.raises(AutonomousPurchaseProhibitedError) as exc_info:
        engine.record_cost_metric(actual_incurred_spend_eur=19.99)

    assert "kein Automatik-Kauf" in str(exc_info.value)


def test_calendar_date_alone_does_not_trigger_audit():
    """Calendar dates or time elapsed alone without observable code drift raises error."""
    engine = RetrospectiveSynthesisEngine()

    with pytest.raises(TemporalReAuditTriggerProhibitedError) as exc_info:
        engine.trigger_audit(days_elapsed=30, code_drift_detected=False)

    assert "Kalenderdatum allein löst kein Re-Audit aus" in str(exc_info.value)

    # With code drift, audit is allowed
    assert engine.trigger_audit(days_elapsed=30, code_drift_detected=True) is True


def test_synthesize_progress_deactivates_redundant_tasks_and_surfaces_bottleneck():
    """Synthesizes catalog completion, eliminates manual prompt routing, and surfaces next bottleneck."""
    engine = RetrospectiveSynthesisEngine()

    accepted = [f"CP-{i:02d}" for i in range(1, 51)]
    synthesis = engine.synthesize_progress(accepted_results=accepted, total_catalog_packages=50)

    assert synthesis.catalog_completion.percentage == 100.0
    assert len(synthesis.eliminated_manual_tasks) >= 5
    assert any("Manual prompt routing" in t for t in synthesis.eliminated_manual_tasks)
    assert "PHYSICAL_MAC_EXECUTION_VERIFICATION" in synthesis.next_critical_bottleneck
    assert synthesis.actual_spend_eur == 0.00


def test_evidence_generation():
    """Validates required catalog evidence keys: ['accepted-results', 'actual-usage', 'known-limitations']."""
    engine = RetrospectiveSynthesisEngine()
    engine.synthesize_progress(accepted_results=["CP-01", "CP-50"])

    evidence = engine.generate_retrospective_evidence()

    assert "accepted-results" in evidence
    assert "actual-usage" in evidence
    assert "known-limitations" in evidence

    assert "CP-01" in evidence["accepted-results"]
    assert evidence["actual-usage"]["spend_eur"] == 0.00
    assert len(evidence["known-limitations"]) >= 2
