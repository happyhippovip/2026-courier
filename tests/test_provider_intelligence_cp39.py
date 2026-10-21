"""Tests for CP-39 / CQ-39 / GB-PROVIDER-INTEL-01: Provider Intelligence Evaluator & Actionability Boundary.

Verifies:
1. Grounding in official primary source citations and fetch timestamps.
2. Already handled capabilities trigger zero builds ("ALREADY_HANDLED erzeugt keinen Build").
3. Speculative hypotheses are filtered out as irrelevant churn.
4. Genuinely new material findings target specific adapters with measurable goals and 0.00 EUR budget gates.
5. Evidence generated with ['primary-source', 'prior-finding', 'relevant-adapter'].
"""

import pytest

from courier_core.provider_intelligence_evaluator import (
    FindingStatus,
    MissingSourceCitationError,
    ProviderFinding,
    ProviderIntelligenceEvaluator,
    SourceType,
)


def test_missing_source_or_fetch_date_raises_error():
    """Findings lacking verifiable source URI or fetch date raise MissingSourceCitationError."""
    evaluator = ProviderIntelligenceEvaluator()

    bad_finding = ProviderFinding(
        finding_id="f-bad",
        provider="google",
        source_uri="",  # Missing URI
        fetch_date_iso="2026-10-21T12:00:00Z",
        source_type=SourceType.PRIMARY_OFFICIAL_SOURCE,
        claimed_feature="new_feature",
        target_adapter="google_gemini_adapter",
    )

    with pytest.raises(MissingSourceCitationError):
        evaluator.evaluate_finding(bad_finding)


def test_already_handled_finding_triggers_zero_builds():
    """Announcements for already-implemented features yield ALREADY_HANDLED and triggers_build = False."""
    evaluator = ProviderIntelligenceEvaluator()

    handled_finding = ProviderFinding(
        finding_id="f-handled-01",
        provider="google",
        source_uri="https://ai.google.dev/release-notes/2026-10",
        fetch_date_iso="2026-10-21T12:00:00Z",
        source_type=SourceType.PRIMARY_OFFICIAL_SOURCE,
        claimed_feature="structured_output",  # Already present in google_gemini_adapter
        target_adapter="google_gemini_adapter",
    )

    dec = evaluator.evaluate_finding(handled_finding)

    assert dec.status == FindingStatus.ALREADY_HANDLED
    assert dec.triggers_build is False
    assert "already handled" in dec.rationale


def test_speculative_hypothesis_marked_irrelevant_churn():
    """Unverified rumors or speculative social media posts do not trigger builds."""
    evaluator = ProviderIntelligenceEvaluator()

    speculative = ProviderFinding(
        finding_id="f-spec-01",
        provider="openai",
        source_uri="https://twitter.com/ai_rumors/123",
        fetch_date_iso="2026-10-21T12:00:00Z",
        source_type=SourceType.SPECULATIVE_HYPOTHESIS,
        claimed_feature="mythical_reasoning_mode",
        target_adapter="openai_adapter",
    )

    dec = evaluator.evaluate_finding(speculative)

    assert dec.status == FindingStatus.IRRELEVANT_CHURN
    assert dec.triggers_build is False


def test_material_new_finding_targets_specific_adapter_with_budget_gate():
    """Grounded primary findings introduce measurable goals with 0.00 EUR budget gates."""
    evaluator = ProviderIntelligenceEvaluator()

    new_finding = ProviderFinding(
        finding_id="f-new-01",
        provider="anthropic",
        source_uri="https://docs.anthropic.com/en/release-notes",
        fetch_date_iso="2026-10-21T12:00:00Z",
        source_type=SourceType.PRIMARY_OFFICIAL_SOURCE,
        claimed_feature="ephemeral_session_token",
        target_adapter="anthropic_adapter",
    )

    dec = evaluator.evaluate_finding(new_finding)

    assert dec.status == FindingStatus.MATERIAL_ACTIONABLE
    assert dec.triggers_build is True
    assert dec.target_adapter == "anthropic_adapter"
    assert dec.budget_gate_eur == 0.00
    assert "ephemeral_session_token" in (dec.measurable_goal or "")


def test_evidence_generation():
    """Emits required evidence with primary-source, prior-finding, and relevant-adapter."""
    evaluator = ProviderIntelligenceEvaluator()
    finding = ProviderFinding(
        finding_id="f-evid",
        provider="google",
        source_uri="https://ai.google.dev/docs",
        fetch_date_iso="2026-10-21T12:00:00Z",
        source_type=SourceType.PRIMARY_OFFICIAL_SOURCE,
        claimed_feature="context_caching",
        target_adapter="google_gemini_adapter",
    )
    evaluator.evaluate_finding(finding)

    evidence = evaluator.generate_provider_intel_evidence()
    required_keys = ["primary-source", "prior-finding", "relevant-adapter"]
    for k in required_keys:
        assert k in evidence

    assert evidence["primary-source"]["fetch_dates_verified"] is True
    assert evidence["relevant-adapter"]["budget_gate_eur"] == "0.00"
    assert "google_gemini_adapter" in evidence["relevant-adapter"]["monitored_adapters"]
