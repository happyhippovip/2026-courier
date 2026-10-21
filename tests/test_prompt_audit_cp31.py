"""Tests for CP-31 / CQ-31 / GB-PROMPT-AUDIT-01: Prompt Effect Auditor & Capability Consistency.

Verifies:
1. Consistent prompt packages are marked EXECUTABLE.
2. Inconsistent entries (read-only label with shell or mutation effects) are marked NON_EXECUTABLE.
3. Underreported risk tiers are flagged and blocked.
4. Corrective deltas transition status to DELTA_PROPOSED without mutating stable package IDs.
5. Evidence generated with ['prompt-registry', 'capability-schema', 'effect-policy'].
"""

import pytest

from courier_core.prompt_effect_auditor import (
    DeclaredEffect,
    ExecutableStatus,
    PromptEffectAuditor,
    PromptPackageEntry,
    RiskTier,
)


def test_consistent_entry_remains_executable():
    """Consistent declared and actual effects remain EXECUTABLE."""
    auditor = PromptEffectAuditor()
    entry = PromptPackageEntry(
        package_id="CP-01",
        version="1.0.0",
        prompt_text="Inspect current verified repository and acceptance baseline.",
        declared_effects={DeclaredEffect.READ_ONLY, DeclaredEffect.INSPECTION},
        declared_risk=RiskTier.LOW,
        actual_effects={DeclaredEffect.READ_ONLY, DeclaredEffect.INSPECTION},
    )
    auditor.register_package(entry)
    audited = auditor.audit_entry("CP-01")

    assert audited.status == ExecutableStatus.EXECUTABLE
    assert len(audited.inconsistency_reasons) == 0


def test_read_only_mismatch_with_shell_marked_non_executable():
    """An entry claiming read-only that invokes shell or tests is marked NON_EXECUTABLE."""
    auditor = PromptEffectAuditor()
    entry = PromptPackageEntry(
        package_id="CP-FAKE-READ",
        version="1.0.0",
        prompt_text="Just read the logs and run tests in a shell.",
        declared_effects={DeclaredEffect.READ_ONLY},
        declared_risk=RiskTier.LOW,
        actual_effects={DeclaredEffect.READ_ONLY, DeclaredEffect.SHELL_EXECUTION},
    )
    auditor.register_package(entry)
    audited = auditor.audit_entry("CP-FAKE-READ")

    assert audited.status == ExecutableStatus.NON_EXECUTABLE
    assert any("requires active effects" in r for r in audited.inconsistency_reasons)


def test_low_risk_underreporting_marked_non_executable():
    """An entry declaring LOW risk but having mutating file writes is marked NON_EXECUTABLE."""
    auditor = PromptEffectAuditor()
    entry = PromptPackageEntry(
        package_id="CP-MUTATE-LOW",
        version="1.0.0",
        prompt_text="Write changes to disk.",
        declared_effects={DeclaredEffect.MUTATING_WRITE},
        declared_risk=RiskTier.LOW,  # Inconsistent: mutating write cannot be LOW risk
        actual_effects={DeclaredEffect.MUTATING_WRITE},
    )
    auditor.register_package(entry)
    audited = auditor.audit_entry("CP-MUTATE-LOW")

    assert audited.status == ExecutableStatus.NON_EXECUTABLE
    assert any("Declared risk is LOW but actual effects include file mutation" in r for r in audited.inconsistency_reasons)


def test_delta_proposal_transitions_status_to_delta_proposed():
    """Proposing a corrective delta updates the status to DELTA_PROPOSED preserving stable ID."""
    auditor = PromptEffectAuditor()
    entry = PromptPackageEntry(
        package_id="CP-NEEDS-FIX",
        version="1.2.0",
        prompt_text="Write new adapter code.",
        declared_effects={DeclaredEffect.READ_ONLY},
        declared_risk=RiskTier.LOW,
        actual_effects={DeclaredEffect.MUTATING_WRITE},
    )
    auditor.register_package(entry)
    auditor.audit_entry("CP-NEEDS-FIX")
    assert entry.status == ExecutableStatus.NON_EXECUTABLE

    # Propose delta with accurate effects and risk
    updated = auditor.propose_delta(
        package_id="CP-NEEDS-FIX",
        corrected_effects={DeclaredEffect.MUTATING_WRITE},
        corrected_risk=RiskTier.MEDIUM,
    )
    assert updated.status == ExecutableStatus.DELTA_PROPOSED
    assert updated.package_id == "CP-NEEDS-FIX"
    assert updated.version == "1.2.0"
    assert updated.declared_risk == RiskTier.MEDIUM


def test_evidence_generation():
    """Emits required evidence with prompt-registry, capability-schema, and effect-policy."""
    auditor = PromptEffectAuditor()
    entry = PromptPackageEntry(
        package_id="CP-EVID",
        version="1.0.0",
        prompt_text="Simple inspection",
        declared_effects={DeclaredEffect.READ_ONLY},
        declared_risk=RiskTier.LOW,
        actual_effects={DeclaredEffect.READ_ONLY},
    )
    auditor.register_package(entry)
    auditor.audit_entry("CP-EVID")

    evidence = auditor.generate_prompt_audit_evidence()
    required_keys = ["prompt-registry", "capability-schema", "effect-policy"]
    for k in required_keys:
        assert k in evidence

    assert "CP-EVID" in evidence["prompt-registry"]
    assert evidence["effect-policy"]["read_only_strictly_enforced"] is True
    assert evidence["effect-policy"]["inconsistent_entries_non_executable"] is True
