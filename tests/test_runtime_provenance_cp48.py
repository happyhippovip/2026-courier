"""Tests for CP-48 / CQ-48 / GB-CROSS-PLATFORM-IDENTITY-01: Runtime Provenance & Cross-Platform Binder.

Verifies:
1. Unpushed/unloaded candidate is never marked deployed ("Ungepushed/unloaded ist nicht deployed").
2. Windows tests cannot certify Mac deployments without physical Mac proof ("keine Mac-Behauptung aus Windows-Test").
3. Local tree gaps, dirty files, and unpushed commits are explicitly enumerated ("lokale Lücken werden exakt benannt").
4. Simulated hardware receipts are strictly forbidden.
5. Evidence structure generation containing ['candidate-ref', 'runtime-digest', 'physical-evidence'].
"""

import pytest

from courier_core.runtime_provenance_verifier import (
    CandidateRef,
    CrossPlatformSimulationProhibitedError,
    DeploymentReadiness,
    PhysicalWorkerReceipt,
    PlatformKind,
    RuntimeDigest,
    RuntimeProvenanceVerifier,
)


def test_unpushed_local_only_cannot_be_deployed():
    """Unpushed commits are classified as UNPUSHED_LOCAL_ONLY and cannot be deployed."""
    verifier = RuntimeProvenanceVerifier()

    candidate = CandidateRef(
        repo_name="2026-courier",
        branch="feature-x",
        local_sha="abc1234567",
        remote_sha=None,  # Not pushed
        is_dirty=False,
    )
    runtime = RuntimeDigest(
        config_sha256="cfg-hash",
        binary_sha256="bin-hash",
        loaded_at_iso="2026-10-21T12:00:00Z",
        loaded_sha="abc1234567",
    )
    receipt = PhysicalWorkerReceipt(
        receipt_id="rec-win-1",
        host_platform=PlatformKind.WINDOWS,
        os_version="10.0.26100",
        machine_arch="x86_64",
        executed_at_iso="2026-10-21T12:05:00Z",
    )

    res = verifier.verify_provenance_chain(candidate, runtime, receipt, target_platform=PlatformKind.WINDOWS)

    assert res["readiness"] == DeploymentReadiness.UNPUSHED_LOCAL_ONLY.value
    assert res["is_deployable"] is False
    assert any("not been pushed" in g for g in res["detected_gaps"])


def test_dirty_worktree_cannot_be_deployed():
    """Dirty worktree cannot be marked deployed; local uncommitted gaps are explicitly itemized."""
    verifier = RuntimeProvenanceVerifier()

    candidate = CandidateRef(
        repo_name="2026-courier",
        branch="main",
        local_sha="sha999",
        remote_sha="sha999",
        is_dirty=True,  # Modified files
        untracked_files=["temp.py"],
    )
    runtime = RuntimeDigest(
        config_sha256="cfg",
        binary_sha256=None,
        loaded_at_iso="2026-10-21T12:00:00Z",
        loaded_sha="sha999",
    )
    receipt = PhysicalWorkerReceipt(
        receipt_id="rec-win-2",
        host_platform=PlatformKind.WINDOWS,
        os_version="10.0.26100",
        machine_arch="x86_64",
        executed_at_iso="2026-10-21T12:05:00Z",
    )

    res = verifier.verify_provenance_chain(candidate, runtime, receipt, target_platform=PlatformKind.WINDOWS)

    assert res["readiness"] == DeploymentReadiness.UNCOMMITTED_DIRTY.value
    assert res["is_deployable"] is False
    assert any("uncommitted modified files" in g for g in res["detected_gaps"])
    assert any("untracked files" in g for g in res["detected_gaps"])


def test_claiming_mac_from_windows_test_raises_cross_platform_error():
    """Attempting to certify a Mac target using Windows physical worker evidence is strictly prohibited."""
    verifier = RuntimeProvenanceVerifier()

    candidate = CandidateRef(
        repo_name="2026-courier",
        branch="main",
        local_sha="bound_sha_123",
        remote_sha="bound_sha_123",
        is_dirty=False,
    )
    runtime = RuntimeDigest(
        config_sha256="cfg",
        binary_sha256=None,
        loaded_at_iso="2026-10-21T12:00:00Z",
        loaded_sha="bound_sha_123",
    )
    # Physical receipt from Windows machine
    receipt = PhysicalWorkerReceipt(
        receipt_id="rec-win-3",
        host_platform=PlatformKind.WINDOWS,
        os_version="Windows 11",
        machine_arch="x86_64",
        executed_at_iso="2026-10-21T12:05:00Z",
    )

    # Claiming Mac certification from Windows receipt MUST raise error!
    with pytest.raises(CrossPlatformSimulationProhibitedError) as exc_info:
        verifier.verify_provenance_chain(candidate, runtime, receipt, target_platform=PlatformKind.DARWIN_MAC)

    assert "keine Mac-Behauptung aus Windows-Test" in str(exc_info.value)


def test_simulated_receipt_strictly_rejected():
    """Simulated hardware receipts raise CrossPlatformSimulationProhibitedError."""
    verifier = RuntimeProvenanceVerifier()

    candidate = CandidateRef(
        repo_name="2026-courier",
        branch="main",
        local_sha="sha-a",
        remote_sha="sha-a",
        is_dirty=False,
    )
    runtime = RuntimeDigest(
        config_sha256="cfg",
        binary_sha256=None,
        loaded_at_iso="2026-10-21T12:00:00Z",
        loaded_sha="sha-a",
    )
    fake_receipt = PhysicalWorkerReceipt(
        receipt_id="fake-rec",
        host_platform=PlatformKind.WINDOWS,
        os_version="fake-os",
        machine_arch="x86_64",
        executed_at_iso="2026-10-21T12:05:00Z",
        is_simulated=True,  # Fake!
    )

    with pytest.raises(CrossPlatformSimulationProhibitedError):
        verifier.verify_provenance_chain(candidate, runtime, fake_receipt, target_platform=PlatformKind.WINDOWS)


def test_verified_matching_windows_chain_succeeds():
    """Matching 3-way SHA with authentic Windows receipt verifies as deployable."""
    verifier = RuntimeProvenanceVerifier()

    candidate = CandidateRef(
        repo_name="2026-courier",
        branch="grokbot/gb-windows-ready",
        local_sha="777aaa888",
        remote_sha="777aaa888",
        is_dirty=False,
    )
    runtime = RuntimeDigest(
        config_sha256="cfg-valid",
        binary_sha256="bin-valid",
        loaded_at_iso="2026-10-21T12:00:00Z",
        loaded_sha="777aaa888",
    )
    receipt = PhysicalWorkerReceipt(
        receipt_id="rec-win-authentic",
        host_platform=PlatformKind.WINDOWS,
        os_version="10.0.26100",
        machine_arch="x86_64",
        executed_at_iso="2026-10-21T12:05:00Z",
    )

    res = verifier.verify_provenance_chain(candidate, runtime, receipt, target_platform=PlatformKind.WINDOWS)

    assert res["readiness"] == DeploymentReadiness.VERIFIED_DEPLOYABLE.value
    assert res["is_deployable"] is True
    assert len(res["detected_gaps"]) == 0


def test_evidence_generation():
    """Validates required catalog evidence keys: ['candidate-ref', 'runtime-digest', 'physical-evidence']."""
    verifier = RuntimeProvenanceVerifier()

    candidate = CandidateRef(
        repo_name="2026-courier",
        branch="main",
        local_sha="sha-test",
        remote_sha="sha-test",
        is_dirty=False,
    )
    runtime = RuntimeDigest(
        config_sha256="cfg",
        binary_sha256=None,
        loaded_at_iso="2026-10-21T12:00:00Z",
        loaded_sha="sha-test",
    )
    receipt = PhysicalWorkerReceipt(
        receipt_id="rec-test",
        host_platform=PlatformKind.WINDOWS,
        os_version="10.0.26100",
        machine_arch="x86_64",
        executed_at_iso="2026-10-21T12:05:00Z",
    )

    verifier.verify_provenance_chain(candidate, runtime, receipt, target_platform=PlatformKind.WINDOWS)
    evidence = verifier.generate_provenance_evidence()

    assert "candidate-ref" in evidence
    assert "runtime-digest" in evidence
    assert "physical-evidence" in evidence

    assert evidence["candidate-ref"]["candidate_sha"] == "sha-test"
    assert evidence["runtime-digest"]["readiness"] == "VERIFIED_DEPLOYABLE"
    assert evidence["physical-evidence"]["host_platform"] == "WINDOWS"
    assert evidence["physical-evidence"]["is_deployable"] is True
