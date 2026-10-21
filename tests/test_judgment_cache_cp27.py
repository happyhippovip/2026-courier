"""Tests for CP-27 / CQ-27 / GB-JUDGMENT-01: Judgment Cache & Surgical Invalidation

Verifies:
1. Cosmetic changes (trailing spaces, line ending differences) do not trigger re-review (valid reuse).
2. Code artifact modifications surgically invalidate only the affected component.
3. Policy version changes invalidate prior review judgments.
4. Test suite fingerprint changes invalidate prior reviews.
5. Composite cache key enforces multi-dimensional identity beyond report file hash.
6. Evidence generated with ['judgment-cache', 'dependency-manifest', 'accepted-review'].
"""

import pytest

from courier_core.judgment_cache_engine import (
    InvalidationReason,
    JudgmentCacheEngine,
    JudgmentDependencyManifest,
    hash_content,
    normalize_content_cosmetics,
)


def test_cosmetic_changes_do_not_trigger_review_reuse_judgment():
    engine = JudgmentCacheEngine()

    code_original = "def compute(x):\n    return x * 2\n"
    # Cosmetic variant with Windows CRLF, trailing spaces, and blank lines
    code_cosmetic = "def compute(x):  \r\n    return x * 2   \r\n\r\n"

    hash_orig = hash_content(code_original, normalize=True)
    hash_cosm = hash_content(code_cosmetic, normalize=True)

    assert hash_orig == hash_cosm

    manifest_orig = JudgmentDependencyManifest(
        component_id="calc-service",
        artifact_content_hash=hash_orig,
        input_spec_hash="spec-v1",
        policy_version_hash="policy-v10",
        test_suite_fingerprint="tests-passing-100",
        runtime_platform_id="windows-x64",
    )

    # Record initial review pass
    engine.record_judgment(
        manifest=manifest_orig,
        verdict="PASS",
        accepted_review_id="rev-calc-101",
        reviewer_identity="courier-verifier",
    )

    # Candidate with cosmetic modification checks validity
    manifest_cosmetic = JudgmentDependencyManifest(
        component_id="calc-service",
        artifact_content_hash=hash_cosm,  # Identical normalized hash
        input_spec_hash="spec-v1",
        policy_version_hash="policy-v10",
        test_suite_fingerprint="tests-passing-100",
        runtime_platform_id="windows-x64",
    )

    valid, judgment, reason, msg = engine.evaluate_judgment_validity(manifest_cosmetic)

    assert valid is True
    assert reason == InvalidationReason.VALID_REUSE
    assert judgment.accepted_review_id == "rev-calc-101"


def test_artifact_change_surgically_invalidates_only_affected_component():
    engine = JudgmentCacheEngine()

    # Component A: Router
    manifest_a = JudgmentDependencyManifest(
        component_id="router",
        artifact_content_hash="hash-router-v1",
        input_spec_hash="spec-1",
        policy_version_hash="pol-1",
        test_suite_fingerprint="tests-1",
        runtime_platform_id="windows-x64",
    )
    # Component B: Auth
    manifest_b = JudgmentDependencyManifest(
        component_id="auth",
        artifact_content_hash="hash-auth-v1",
        input_spec_hash="spec-1",
        policy_version_hash="pol-1",
        test_suite_fingerprint="tests-1",
        runtime_platform_id="windows-x64",
    )

    engine.record_judgment(manifest_a, "PASS", "rev-router-1", "verifier-1")
    engine.record_judgment(manifest_b, "PASS", "rev-auth-1", "verifier-1")

    # Modify Router code artifact
    manifest_a_updated = JudgmentDependencyManifest(
        component_id="router",
        artifact_content_hash="hash-router-v2",  # Code changed!
        input_spec_hash="spec-1",
        policy_version_hash="pol-1",
        test_suite_fingerprint="tests-1",
        runtime_platform_id="windows-x64",
    )

    # Router review is invalidated
    valid_a, j_a, reason_a, _ = engine.evaluate_judgment_validity(manifest_a_updated)
    assert valid_a is False
    assert reason_a == InvalidationReason.ARTIFACT_CHANGED

    # Auth review remains perfectly VALID (surgical component isolation)
    valid_b, j_b, reason_b, _ = engine.evaluate_judgment_validity(manifest_b)
    assert valid_b is True
    assert reason_b == InvalidationReason.VALID_REUSE


def test_policy_change_invalidates_judgment():
    engine = JudgmentCacheEngine()

    manifest = JudgmentDependencyManifest(
        component_id="core-service",
        artifact_content_hash="hash-c1",
        input_spec_hash="spec-1",
        policy_version_hash="pol-v1",
        test_suite_fingerprint="tests-1",
        runtime_platform_id="windows-x64",
    )
    engine.record_judgment(manifest, "PASS", "rev-1", "verifier-1")

    # Policy updated
    manifest_policy_change = JudgmentDependencyManifest(
        component_id="core-service",
        artifact_content_hash="hash-c1",
        input_spec_hash="spec-1",
        policy_version_hash="pol-v2-hardened",
        test_suite_fingerprint="tests-1",
        runtime_platform_id="windows-x64",
    )

    valid, _, reason, _ = engine.evaluate_judgment_validity(manifest_policy_change)
    assert valid is False
    assert reason == InvalidationReason.POLICY_CHANGED


def test_test_suite_fingerprint_change_invalidates_judgment():
    engine = JudgmentCacheEngine()

    manifest = JudgmentDependencyManifest(
        component_id="core-service",
        artifact_content_hash="hash-c1",
        input_spec_hash="spec-1",
        policy_version_hash="pol-v1",
        test_suite_fingerprint="tests-hash-old",
        runtime_platform_id="windows-x64",
    )
    engine.record_judgment(manifest, "PASS", "rev-1", "verifier-1")

    # Tests modified or regressed
    manifest_tests_change = JudgmentDependencyManifest(
        component_id="core-service",
        artifact_content_hash="hash-c1",
        input_spec_hash="spec-1",
        policy_version_hash="pol-v1",
        test_suite_fingerprint="tests-hash-new",
        runtime_platform_id="windows-x64",
    )

    valid, _, reason, _ = engine.evaluate_judgment_validity(manifest_tests_change)
    assert valid is False
    assert reason == InvalidationReason.TESTS_CHANGED


def test_evidence_generation():
    engine = JudgmentCacheEngine()

    manifest = JudgmentDependencyManifest(
        component_id="evidence-component",
        artifact_content_hash="art-sha",
        input_spec_hash="spec-sha",
        policy_version_hash="pol-sha",
        test_suite_fingerprint="test-sha",
        runtime_platform_id="win-py312",
    )

    evidence = engine.generate_judgment_evidence(manifest, review_id="rev-ev-101")

    assert evidence["required_evidence"] == ["judgment-cache", "dependency-manifest", "accepted-review"]
    assert evidence["judgment-cache"]["cached_entries_count"] == 1
    assert evidence["dependency-manifest"]["component_id"] == "evidence-component"
    assert evidence["accepted-review"]["verdict"] == "PASS"
    assert evidence["accepted-review"]["accepted_review_id"] == "rev-ev-101"
