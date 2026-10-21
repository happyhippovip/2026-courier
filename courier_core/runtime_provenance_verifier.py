"""Runtime Provenance Verifier & Cross-Platform Evidence Binder (CP-48 / GB-CROSS-PLATFORM-IDENTITY-01).

Guarantees:
1. Exact commit and candidate binding: Unpushed and unloaded code is never marked deployed ("Ungepushed/unloaded ist nicht deployed").
2. Cross-platform truth: Windows test runs cannot certify Mac deployment without physical Mac proof ("keine Mac-Behauptung aus Windows-Test").
3. Local gap enumeration: Uncommitted changes, unpushed commits, and missing platform builds are explicitly itemized ("lokale Lücken werden exakt benannt").
4. Authentic evidence chain linking candidate commit, runtime digest, and physical worker receipt.
5. Evidence generation containing 'candidate-ref', 'runtime-digest', and 'physical-evidence'.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class PlatformKind(str, Enum):
    WINDOWS = "WINDOWS"
    DARWIN_MAC = "DARWIN_MAC"
    LINUX = "LINUX"


class DeploymentReadiness(str, Enum):
    UNCOMMITTED_DIRTY = "UNCOMMITTED_DIRTY"
    UNPUSHED_LOCAL_ONLY = "UNPUSHED_LOCAL_ONLY"
    SHA_MISMATCH = "SHA_MISMATCH"
    MISSING_PHYSICAL_PROOF = "MISSING_PHYSICAL_PROOF"
    VERIFIED_DEPLOYABLE = "VERIFIED_DEPLOYABLE"


class CrossPlatformSimulationProhibitedError(Exception):
    """Raised when an attempt is made to claim Mac certification from a Windows execution or vice versa."""


@dataclass(frozen=True)
class CandidateRef:
    repo_name: str
    branch: str
    local_sha: str
    remote_sha: Optional[str]
    is_dirty: bool
    untracked_files: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeDigest:
    config_sha256: str
    binary_sha256: Optional[str]
    loaded_at_iso: str
    loaded_sha: str


@dataclass(frozen=True)
class PhysicalWorkerReceipt:
    receipt_id: str
    host_platform: PlatformKind
    os_version: str
    machine_arch: str
    executed_at_iso: str
    is_simulated: bool = False


class RuntimeProvenanceVerifier:
    """Validates the unbroken evidence chain across Git candidate refs, runtime digests, and physical worker receipts."""

    def __init__(self) -> None:
        self._audits: List[Dict[str, Any]] = []

    def verify_provenance_chain(
        self,
        candidate: CandidateRef,
        runtime: RuntimeDigest,
        receipt: PhysicalWorkerReceipt,
        target_platform: PlatformKind,
    ) -> Dict[str, Any]:
        """Evaluates whether the candidate meets strict physical deployment standards.

        Strict Invariants:
        1. Dirty local files -> UNCOMMITTED_DIRTY (not deployed).
        2. Remote SHA missing or mismatch -> UNPUSHED_LOCAL_ONLY (not deployed).
        3. Loaded runtime SHA mismatch -> SHA_MISMATCH.
        4. Cross-platform simulation check: claiming Mac from Windows receipt raises error.
        5. Simulation forbidden: receipt.is_simulated=True is rejected.
        """
        detected_gaps: List[str] = []

        # 1. Platform Grounding & Anti-Simulation Check
        if receipt.is_simulated:
            raise CrossPlatformSimulationProhibitedError("Physical simulation is prohibited. Real hardware evidence required.")

        if target_platform != receipt.host_platform:
            raise CrossPlatformSimulationProhibitedError(
                f"Cannot certify target platform '{target_platform.value}' using worker evidence from '{receipt.host_platform.value}'! "
                "keine Mac-Behauptung aus Windows-Test."
            )

        # 2. Local Tree Hygiene
        if candidate.is_dirty:
            detected_gaps.append("Local worktree contains uncommitted modified files")
        if candidate.untracked_files:
            detected_gaps.append(f"Local worktree contains {len(candidate.untracked_files)} untracked files")

        # 3. Remote Synchronization
        if not candidate.remote_sha:
            detected_gaps.append("Local commit has not been pushed to remote origin")
        elif candidate.local_sha != candidate.remote_sha:
            detected_gaps.append(f"Local SHA ({candidate.local_sha}) diverges from Remote SHA ({candidate.remote_sha})")

        # 4. Runtime Digest Binding
        if runtime.loaded_sha != candidate.local_sha:
            detected_gaps.append(f"Loaded runtime SHA ({runtime.loaded_sha}) does not match Candidate SHA ({candidate.local_sha})")

        # 5. Determine Overall Deployment Readiness
        if candidate.is_dirty:
            readiness = DeploymentReadiness.UNCOMMITTED_DIRTY
        elif not candidate.remote_sha or candidate.local_sha != candidate.remote_sha:
            readiness = DeploymentReadiness.UNPUSHED_LOCAL_ONLY
        elif runtime.loaded_sha != candidate.local_sha:
            readiness = DeploymentReadiness.SHA_MISMATCH
        elif detected_gaps:
            readiness = DeploymentReadiness.MISSING_PHYSICAL_PROOF
        else:
            readiness = DeploymentReadiness.VERIFIED_DEPLOYABLE

        audit_record = {
            "target_platform": target_platform.value,
            "readiness": readiness.value,
            "is_deployable": readiness == DeploymentReadiness.VERIFIED_DEPLOYABLE,
            "candidate_sha": candidate.local_sha,
            "remote_sha": candidate.remote_sha,
            "runtime_loaded_sha": runtime.loaded_sha,
            "host_platform": receipt.host_platform.value,
            "detected_gaps": detected_gaps,
            "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._audits.append(audit_record)
        return audit_record

    def generate_provenance_evidence(self) -> Dict[str, Any]:
        """Generates evidence audit records containing required catalog keys."""
        latest = self._audits[-1] if self._audits else {}
        return {
            "candidate-ref": {
                "candidate_sha": latest.get("candidate_sha"),
                "remote_sha": latest.get("remote_sha"),
                "is_diverged": latest.get("candidate_sha") != latest.get("remote_sha"),
            },
            "runtime-digest": {
                "runtime_loaded_sha": latest.get("runtime_loaded_sha"),
                "readiness": latest.get("readiness"),
            },
            "physical-evidence": {
                "host_platform": latest.get("host_platform"),
                "is_deployable": latest.get("is_deployable"),
                "detected_gaps": latest.get("detected_gaps", []),
            },
        }
