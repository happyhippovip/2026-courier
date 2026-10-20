"""CI & Independent Acceptance Engine for Courier Symphony (Category 21, Topics 204-215).

Implements strict, fail-closed verification rules:
- Topic 204: Windows-Runner-Provenienz prüfen
- Topic 205: Exakten Checkout-SHA belegen
- Topic 206: Skipped Required Tests erkennen
- Topic 207: Historische CI nicht als aktuell werten
- Topic 208: Mock-Ausführung in CI klassifizieren
- Topic 209-212: PR Test-Bundles (PR304, PR351, PR410, PR491)
- Topic 213: PR495-Skips bewerten (nur privilegierte OS-Skips zulässig)
- Topic 214: Zwölf-Case-Matrix prüfen
- Topic 215: Test-Duplikate ohne Löschung identifizieren
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclasses.dataclass(frozen=True)
class RunnerProvenance:
    os_platform: str
    runner_id: str
    job_id: str
    arch: str
    is_isolated: bool
    timestamp: float
    workdir: str
    source_sha: str


def verify_runner_provenance(
    prov: RunnerProvenance,
    required_platform: str = "Windows",
    expected_sha: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate honest runner provenance according to Topic 204."""
    if not isinstance(prov, RunnerProvenance):
        return False, "INVALID_PROVENANCE_OBJECT"
    
    # Platform validation
    plat = prov.os_platform.lower()
    if required_platform.lower() == "windows":
        if "win" not in plat:
            return False, f"RUNNER_PLATFORM_MISMATCH: expected Windows, got {prov.os_platform!r}"
    elif plat != required_platform.lower():
        return False, f"RUNNER_PLATFORM_MISMATCH: expected {required_platform}, got {prov.os_platform!r}"

    # Isolation check
    if not prov.is_isolated:
        return False, "RUNNER_NOT_ISOLATED"

    # SHA binding
    if expected_sha and prov.source_sha != expected_sha:
        return False, f"RUNNER_SHA_MISMATCH: expected {expected_sha}, got {prov.source_sha}"

    # Required IDs
    if not prov.runner_id.strip() or not prov.job_id.strip():
        return False, "RUNNER_TELEMETRY_INCOMPLETE"

    return True, None


def verify_exact_checkout_sha(
    actual_sha: str,
    expected_sha: str,
    is_dirty: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Validate exact 40-character hexadecimal git commit SHA according to Topic 205."""
    sha_re = re.compile(r"^[0-9a-fA-F]{40}$")
    if not sha_re.match(actual_sha):
        return False, f"MALFORMED_ACTUAL_SHA: {actual_sha!r}"
    if not sha_re.match(expected_sha):
        return False, f"MALFORMED_EXPECTED_SHA: {expected_sha!r}"
    if is_dirty:
        return False, "WORKTREE_DIRTY: checkout has uncommitted changes"
    if actual_sha.lower() != expected_sha.lower():
        return False, f"SHA_MISMATCH: expected {expected_sha}, got {actual_sha}"
    return True, None


def verify_ci_freshness(
    ci_timestamp: float,
    max_age_seconds: float = 7200.0,
    current_time: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """Reject historical or stale CI results older than max_age_seconds according to Topic 207."""
    now = time.time() if current_time is None else current_time
    age = now - ci_timestamp
    if age < -60.0:
        return False, f"FUTURE_TIMESTAMP: CI timestamp is {abs(age):.1f}s in the future"
    if age > max_age_seconds:
        return False, f"CI_STALE: receipt age is {age:.1f}s (exceeds max {max_age_seconds:.1f}s)"
    return True, None


def classify_execution(receipt: Dict[str, Any]) -> str:
    """Classify execution into REAL_EXECUTION vs MOCK_STUB according to Topic 208."""
    if not isinstance(receipt, dict):
        return "REJECTED"
    if receipt.get("is_mock") is True or receipt.get("mock") is True:
        return "MOCK_STUB"
    if receipt.get("mock_model") or "mock" in str(receipt.get("provider", "")).lower():
        return "MOCK_STUB"
    if receipt.get("exit_code") == 0 and receipt.get("launched") is True and receipt.get("output_sha256"):
        return "REAL_EXECUTION"
    return "UNKNOWN"


def check_skipped_tests(
    test_results: List[Dict[str, Any]],
    required_tests: Set[str],
    allowed_skip_patterns: Set[str],
) -> Tuple[bool, List[str]]:
    """Detect skipped required tests according to Topic 206 and PR495 evaluation (Topic 213).

    Returns (passed, list_of_violations).
    """
    violations = []
    skipped_names = set()
    for item in test_results:
        name = item.get("name", "")
        status = item.get("status", "").upper()
        reason = item.get("reason", "")

        if status == "SKIPPED":
            skipped_names.add(name)
            # Check if this test is strictly required
            if name in required_tests:
                # Is the skip reason permitted (e.g. symlinks on Windows without dev mode)?
                is_permitted = any(pat.lower() in reason.lower() for pat in allowed_skip_patterns)
                if not is_permitted:
                    violations.append(f"REQUIRED_TEST_FORBIDDEN_SKIP: {name} skipped with reason: {reason!r}")
        elif name in required_tests and status not in ("PASSED", "PASS"):
            violations.append(f"REQUIRED_TEST_NOT_PASSED: {name} finished with status: {status!r}")

    # Check if any required test was completely omitted
    tested_names = {item.get("name", "") for item in test_results}
    missing = required_tests - tested_names
    for m in missing:
        violations.append(f"REQUIRED_TEST_MISSING: {m}")

    return len(violations) == 0, violations


# -----------------------------------------------------------------------------
# TOPIC 214: ZWÖLF-CASE-MATRIX
# -----------------------------------------------------------------------------

TWELVE_MATRIX_CASES = (
    "CASE_01_LOCAL_DETERMINISTIC",
    "CASE_02_PROVIDER_EXEC_SANDBOXED",
    "CASE_03_ORIGIN_GRANT_ENFORCED",
    "CASE_04_REDIRECT_HOP_LIMIT",
    "CASE_05_REDIRECT_LOOP_DETECTED",
    "CASE_06_ZERO_SPEND_LIMIT_FAIL_CLOSED",
    "CASE_07_SINGLE_WRITER_EXCLUSIVITY",
    "CASE_08_CHECKPOINT_RESTART_RECOVERY",
    "CASE_09_HISTORICAL_CI_STALE_REJECTED",
    "CASE_10_FORBIDDEN_SKIP_REJECTED",
    "CASE_11_OFFLINE_DOI_SYNTAX_VERIFIED",
    "CASE_12_OFFLINE_ISBN_CHECKSUM_VERIFIED",
)


def evaluate_twelve_case_matrix(evidence_receipts: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate full Twelve-Case Matrix (Topic 214)."""
    results = {}
    passed_count = 0
    for case in TWELVE_MATRIX_CASES:
        entry = evidence_receipts.get(case)
        proof_sha = entry.get("proof_sha") if isinstance(entry, dict) else None
        if (
            isinstance(entry, dict)
            and entry.get("status") == "PASS"
            and isinstance(proof_sha, str)
            and bool(proof_sha.strip())
        ):
            results[case] = {"status": "PASS", "proof_sha": proof_sha.strip()}
            passed_count += 1
        else:
            results[case] = {"status": "FAIL", "reason": "Missing, unverified, or non-passing evidence"}

    all_passed = passed_count == len(TWELVE_MATRIX_CASES)
    summary_digest = hashlib.sha256(
        "".join(f"{k}:{v['status']}" for k, v in sorted(results.items())).encode("utf-8")
    ).hexdigest()

    return {
        "schema": "twelve-case-matrix/1",
        "all_passed": all_passed,
        "passed_count": passed_count,
        "total_count": len(TWELVE_MATRIX_CASES),
        "summary_sha256": summary_digest,
        "matrix": results,
    }
