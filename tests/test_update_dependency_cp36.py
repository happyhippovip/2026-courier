"""Tests for CP-36 / CQ-36 / GB-UPDATE-DEPENDENCY-01: Update Dependency Mapper & Surgical Invalidation.

Verifies:
1. Purely cosmetic updates generate 0 Pro calls and invalidate 0 existing judgments.
2. Code changes surgically target only the catalog IDs bound to the modified modules.
3. Unaffected package IDs remain referenced and preserve their historical verified judgments.
4. Evidence generated with ['diff', 'evidence-dependencies', 'catalog-IDs'].
"""

import pytest

from courier_core.update_dependency_mapper import (
    ChangeCategory,
    FileDelta,
    ReevaluationPlan,
    UpdateDependencyMapper,
)


def test_cosmetic_change_triggers_zero_pro_calls_and_zero_invalidations():
    """Cosmetic or docstring edits trigger 0 Pro calls and preserve 100% of existing judgments."""
    mapper = UpdateDependencyMapper()

    deltas = [
        FileDelta(
            path="docs/ARCHITECTURE.md",
            category=ChangeCategory.COSMETIC_DOC,
            lines_added=5,
            lines_removed=2,
            is_cosmetic_only=True,
        ),
        FileDelta(
            path="README.md",
            category=ChangeCategory.COSMETIC_DOC,
            lines_added=1,
            lines_removed=0,
            is_cosmetic_only=True,
        ),
    ]

    plan = mapper.evaluate_delta("sha-cosmetic-01", deltas)

    assert len(plan.affected_catalog_ids) == 0
    assert plan.pro_calls_required == 0
    assert len(plan.unaffected_reused_catalog_ids) == len(mapper.full_catalog_ids)


def test_runtime_lease_change_surgically_targets_bound_packages_only():
    """A code change in runtime_lease.py targets only its bound packages (CP-08, CP-09, CP-11, CP-12)."""
    mapper = UpdateDependencyMapper()

    deltas = [
        FileDelta(
            path="courier_core/runtime_lease.py",
            category=ChangeCategory.CODE,
            lines_added=15,
            lines_removed=3,
            is_cosmetic_only=False,
        ),
    ]

    plan = mapper.evaluate_delta("sha-code-lease-01", deltas)

    expected_affected = {"CP-08", "CP-09", "CP-11", "CP-12"}
    assert set(plan.affected_catalog_ids) == expected_affected
    assert plan.pro_calls_required == 4

    # All other catalog IDs must be preserved as unaffected and reused
    assert "CP-28" in plan.unaffected_reused_catalog_ids
    assert "CP-34" in plan.unaffected_reused_catalog_ids
    assert "CP-35" in plan.unaffected_reused_catalog_ids


def test_evidence_generation():
    """Emits required evidence with diff, evidence-dependencies, and catalog-IDs."""
    mapper = UpdateDependencyMapper()

    deltas = [
        FileDelta(
            path="courier_core/task_handoff.py",
            category=ChangeCategory.CODE,
            lines_added=4,
            lines_removed=1,
        ),
    ]

    plan = mapper.evaluate_delta("sha-handoff-delta", deltas)
    evidence = mapper.generate_dependency_evidence(plan, deltas)

    required_keys = ["diff", "evidence-dependencies", "catalog-IDs"]
    for k in required_keys:
        assert k in evidence

    assert "CP-20" in evidence["catalog-IDs"]["targeted_ids"]
    assert evidence["diff"]["delta_sha"] == "sha-handoff-delta"
    assert evidence["evidence-dependencies"]["zero_pro_call_invariant_verified"] is True
