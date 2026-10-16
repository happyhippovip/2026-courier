"""Unit tests for CI & Independent Acceptance Engine (courier_core/ci_acceptance.py).

Covers Topics 204-215:
- Topic 204: Runner provenance
- Topic 205: Exact checkout SHA
- Topic 206: Skipped required tests
- Topic 207: CI freshness / stale rejection
- Topic 208: Mock classification
- Topic 213: Skip policy evaluation
- Topic 214: Twelve-case matrix
"""

import time
import pytest

from courier_core.ci_acceptance import (
    RunnerProvenance,
    verify_runner_provenance,
    verify_exact_checkout_sha,
    verify_ci_freshness,
    classify_execution,
    check_skipped_tests,
    evaluate_twelve_case_matrix,
    TWELVE_MATRIX_CASES,
)

SAMPLE_SHA_1 = "1c66fd371a645988110d41e358caeb53016e1e2a"
SAMPLE_SHA_2 = "cf70e05863c87f4c541170b0270a41d7c48ec171"


def test_runner_provenance_windows_valid():
    prov = RunnerProvenance(
        os_platform="Windows",
        runner_id="runner-win-01",
        job_id="job-12345",
        arch="AMD64",
        is_isolated=True,
        timestamp=time.time(),
        workdir="C:\\runners\\work",
        source_sha=SAMPLE_SHA_1,
    )
    ok, err = verify_runner_provenance(prov, required_platform="Windows", expected_sha=SAMPLE_SHA_1)
    assert ok is True
    assert err is None


def test_runner_provenance_rejects_non_windows_and_non_isolated():
    # Non-windows platform rejected when Windows required
    prov_linux = RunnerProvenance(
        os_platform="Linux",
        runner_id="runner-linux-01",
        job_id="job-123",
        arch="x86_64",
        is_isolated=True,
        timestamp=time.time(),
        workdir="/work",
        source_sha=SAMPLE_SHA_1,
    )
    ok, err = verify_runner_provenance(prov_linux, required_platform="Windows")
    assert ok is False
    assert "RUNNER_PLATFORM_MISMATCH" in err

    # Un-isolated runner rejected
    prov_unisolated = RunnerProvenance(
        os_platform="Windows",
        runner_id="runner-win-01",
        job_id="job-123",
        arch="AMD64",
        is_isolated=False,
        timestamp=time.time(),
        workdir="C:\\work",
        source_sha=SAMPLE_SHA_1,
    )
    ok, err = verify_runner_provenance(prov_unisolated, required_platform="Windows")
    assert ok is False
    assert "RUNNER_NOT_ISOLATED" in err


def test_runner_provenance_sha_mismatch():
    prov = RunnerProvenance(
        os_platform="Windows",
        runner_id="runner-win-01",
        job_id="job-123",
        arch="AMD64",
        is_isolated=True,
        timestamp=time.time(),
        workdir="C:\\work",
        source_sha=SAMPLE_SHA_1,
    )
    ok, err = verify_runner_provenance(prov, required_platform="Windows", expected_sha=SAMPLE_SHA_2)
    assert ok is False
    assert "RUNNER_SHA_MISMATCH" in err


def test_exact_checkout_sha_verification():
    # Valid matching 40-char hex
    ok, err = verify_exact_checkout_sha(SAMPLE_SHA_1, SAMPLE_SHA_1)
    assert ok is True and err is None

    # Mismatch
    ok, err = verify_exact_checkout_sha(SAMPLE_SHA_1, SAMPLE_SHA_2)
    assert ok is False and "SHA_MISMATCH" in err

    # Dirty worktree
    ok, err = verify_exact_checkout_sha(SAMPLE_SHA_1, SAMPLE_SHA_1, is_dirty=True)
    assert ok is False and "WORKTREE_DIRTY" in err

    # Malformed non-hex SHA
    ok, err = verify_exact_checkout_sha("not-a-sha", SAMPLE_SHA_1)
    assert ok is False and "MALFORMED_ACTUAL_SHA" in err


def test_ci_freshness_check():
    now = 10000.0
    # Fresh receipt (5 minutes old)
    ok, err = verify_ci_freshness(now - 300, max_age_seconds=7200, current_time=now)
    assert ok is True and err is None

    # Stale receipt (> 2 hours old)
    ok, err = verify_ci_freshness(now - 8000, max_age_seconds=7200, current_time=now)
    assert ok is False and "CI_STALE" in err

    # Future timestamp (> 60s in future)
    ok, err = verify_ci_freshness(now + 120, max_age_seconds=7200, current_time=now)
    assert ok is False and "FUTURE_TIMESTAMP" in err


def test_classify_execution():
    # Real execution
    real = {
        "exit_code": 0,
        "launched": True,
        "output_sha256": "def456",
        "provider": "antigravity",
    }
    assert classify_execution(real) == "REAL_EXECUTION"

    # Mock stubs
    mock1 = {"is_mock": True, "exit_code": 0}
    mock2 = {"provider": "mock_provider", "exit_code": 0}
    mock3 = {"mock_model": "test-stub", "exit_code": 0}
    assert classify_execution(mock1) == "MOCK_STUB"
    assert classify_execution(mock2) == "MOCK_STUB"
    assert classify_execution(mock3) == "MOCK_STUB"


def test_check_skipped_tests_policy():
    allowed_patterns = {"symlink", "winerror 1314"}
    required_suite = {"test_security_gate", "test_cost_limit", "test_symlink_escape"}

    # Scenario 1: Allowed skip on Windows symlink privilege
    results_with_allowed_skip = [
        {"name": "test_security_gate", "status": "PASSED"},
        {"name": "test_cost_limit", "status": "PASSED"},
        {"name": "test_symlink_escape", "status": "SKIPPED", "reason": "symlinks not supported or permitted on this host"},
    ]
    ok, violations = check_skipped_tests(results_with_allowed_skip, required_suite, allowed_patterns)
    assert ok is True
    assert violations == []

    # Scenario 2: Forbidden skip on required test
    results_with_forbidden_skip = [
        {"name": "test_security_gate", "status": "SKIPPED", "reason": "too slow for CI"},
        {"name": "test_cost_limit", "status": "PASSED"},
        {"name": "test_symlink_escape", "status": "PASSED"},
    ]
    ok, violations = check_skipped_tests(results_with_forbidden_skip, required_suite, allowed_patterns)
    assert ok is False
    assert any("REQUIRED_TEST_FORBIDDEN_SKIP: test_security_gate" in v for v in violations)

    # Scenario 3: Required test missing from run
    results_missing = [
        {"name": "test_security_gate", "status": "PASSED"},
    ]
    ok, violations = check_skipped_tests(results_missing, required_suite, allowed_patterns)
    assert ok is False
    assert any("REQUIRED_TEST_MISSING: test_cost_limit" in v for v in violations)


def test_twelve_case_matrix_evaluation():
    # Build complete passing evidence dict
    complete_evidence = {
        case: {"status": "PASS", "proof_sha": f"sha_{case}"}
        for case in TWELVE_MATRIX_CASES
    }
    report = evaluate_twelve_case_matrix(complete_evidence)
    assert report["all_passed"] is True
    assert report["passed_count"] == 12
    assert report["total_count"] == 12
    assert report["summary_sha256"]
    assert len(report["matrix"]) == 12

    # Incomplete evidence (one case failing)
    incomplete_evidence = dict(complete_evidence)
    incomplete_evidence["CASE_06_ZERO_SPEND_LIMIT_FAIL_CLOSED"] = {"status": "FAIL", "reason": "over limit"}
    failing_report = evaluate_twelve_case_matrix(incomplete_evidence)
    assert failing_report["all_passed"] is False
    assert failing_report["passed_count"] == 11
    assert failing_report["matrix"]["CASE_06_ZERO_SPEND_LIMIT_FAIL_CLOSED"]["status"] == "FAIL"
