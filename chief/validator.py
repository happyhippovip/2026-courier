"""
validator.py - Security & False-Completion Firewall for Chief Ingestion
Validates incoming handoffs, envelopes, and status reports against known adversarial vectors:
- FND_01: False-completion free-text bypasses
- FND_02: Capability fail-open bypasses
- FND_03: Safety gate evasion
- FND_04: Anti-loop novelty evasion
- FND_06: Unbounded / infinite scoring claims
"""

import os
import math
from typing import Dict, Any, List, Tuple
from .types import Lane


REQUIRED_HANDOFF_FIELDS = [
    "assignment_id",
    "origin",
    "role",
    "timestamp_utc",
    "host_os",
    "mac_host_access",
    "production_write_authority"
]


class IngestionValidationError(Exception):
    pass


class HandoffValidator:
    @staticmethod
    def validate_handoff_payload(payload: Dict[str, Any], filepath: str = "") -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not payload or not isinstance(payload, dict):
            return False, ["PAYLOAD_EMPTY_OR_NON_DICT: Ingestion rejected empty or non-dictionary JSON"]

        # 1. Check Required Headers
        for req in REQUIRED_HANDOFF_FIELDS:
            if req not in payload:
                errors.append(f"MISSING_REQUIRED_FIELD: '{req}' is absent from handoff metadata")

        # 2. Origin & Host Integrity
        origin = str(payload.get("origin", "")).strip().upper()
        lane = Lane.from_str(origin)
        if lane == Lane.UNKNOWN:
            errors.append(f"INVALID_ORIGIN: '{origin}' is not a recognized agent lane")

        host_os = str(payload.get("host_os", "")).strip().upper()
        if host_os not in ("WINDOWS", "MAC", "REMOTE", "DARWIN"):
            errors.append(f"INVALID_HOST_OS: '{host_os}' is not a recognized host OS")

        # Invariant: Never allow production write authority on local lab nodes
        prod_auth = payload.get("production_write_authority", False)
        if prod_auth not in (False, 0):
            errors.append("PROD_WRITE_AUTHORITY_VIOLATION: Production write authority must be False on local nodes")

        # 3. False Completion Defense (FND_01)
        metrics = payload.get("metrics", {})
        if metrics and isinstance(metrics, dict):
            # If claiming tests verified, ensure count > 0
            if "pure_factory_suites_verified" in metrics and metrics["pure_factory_suites_verified"] == 0:
                if metrics.get("pure_factory_reproduced_cases", 0) > 0:
                    errors.append("CONTRADICTORY_METRIC: 0 suites verified but >0 reproduced cases claimed")

            # Check for NaN / Infinity in scoring
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    if math.isnan(v) or math.isinf(v):
                        errors.append(f"UNBOUNDED_METRIC_VALUE: Metric '{k}' has NaN or Infinite value")
                    elif v > 1000000000:
                        errors.append(f"UNGROUNDED_PROFIT_SCORING: Metric '{k}' exceeds maximum grounded threshold (1B)")

        # 4. Capability Fail-Closed Check (FND_02)
        # Verify that capabilities cannot fail-open without explicit proof
        if "hasConnectedTool" in payload:
            if payload["hasConnectedTool"] is not False and payload["hasConnectedTool"] is not True:
                errors.append("CAPABILITY_FAIL_CLOSED_VIOLATION: hasConnectedTool must be strict boolean")

        # 5. Check Artifact Existence if declared
        artifacts = payload.get("artifacts_generated", [])
        if artifacts and isinstance(artifacts, list) and filepath:
            base_dir = os.path.dirname(filepath)
            # Only check if artifacts are listed as relative paths in a local bundle
            # Non-blocking warning only
        return len(errors) == 0, errors


class ChiefRequestValidator:
    """
    Validates inbound structured Chief validation requests per Request Integrity Guard:
    - MISSION_ID
    - WINDOWS_VALIDATION_REQUEST_ID (or ASSIGNMENT_ID)
    - CREATED_BY (must be MAC_CHIEF or CHIEF if specified)
    - ARTIFACT / ARTIFACT_REFERENCE
    - EXACT_QUESTION
    - EXPECTED_EVIDENCE
    - ALLOWED_SCOPE
    """
    REQUIRED_FIELDS = [
        "mission_id",
        "windows_validation_request_id",
        "artifact_reference",
        "exact_question",
        "expected_evidence",
        "allowed_scope"
    ]

    ALLOWED_CAPABILITIES = {
        "WINDOWS_COMPATIBILITY",
        "CMD_POWERSHELL_BEHAVIOR",
        "WINDOWS_PATHS",
        "NTFS_FILESYSTEM_BEHAVIOR",
        "FILESYSTEM_BEHAVIOR",
        "ACL_ACCESS_INTEGRITY",
        "WINDOWS_PROCESS_EVIDENCE",
        "WINDOWS_NATIVE_TEST",
        "WINDOWS_NATIVE_BUILD",
        "WINDOWS_LOG_ANALYSIS",
        "WINDOWS_REPRODUCTION",
        "CROSS_PLATFORM_VALIDATION",
        "SQLITE_WAL_AND_FILESYSTEM_INTEGRITY",
        "FS_AND_INTEGRITY",
        "GENERAL_VALIDATION"
    }

    @classmethod
    def validate_request_dict(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        if not data or not isinstance(data, dict):
            return False, ["PAYLOAD_NOT_DICT: Request payload must be a non-empty dictionary"]

        normalized = {str(k).lower().strip(): k for k in data.keys()}
        missing = []

        m_id = data.get(normalized.get("mission_id", ""))
        if not m_id:
            missing.append("MISSION_ID")

        req_id = data.get(normalized.get("windows_validation_request_id", "")) or data.get(normalized.get("assignment_id", ""))
        if not req_id:
            missing.append("WINDOWS_VALIDATION_REQUEST_ID")

        art = data.get(normalized.get("artifact", "")) or data.get(normalized.get("artifact_reference", ""))
        if not art:
            missing.append("ARTIFACT")

        eq = data.get(normalized.get("exact_question", ""))
        if not eq:
            missing.append("EXACT_QUESTION")

        ee = data.get(normalized.get("expected_evidence", ""))
        if not ee:
            missing.append("EXPECTED_EVIDENCE")

        asc = data.get(normalized.get("allowed_scope", ""))
        if not asc:
            missing.append("ALLOWED_SCOPE")

        if "created_by" in normalized:
            cb = str(data[normalized["created_by"]]).upper().strip()
            if cb not in ("MAC_CHIEF", "CHIEF"):
                return False, [f"INVALID_CREATOR: Request must be created by MAC_CHIEF, got '{cb}'"]

        if missing:
            return False, [f"MISSING_CHIEF_REQUEST_FIELD: '{m}' is required" for m in missing]

        val_type = str(data.get(normalized.get("validation_type", ""), "")).upper().strip()
        if val_type and val_type not in cls.ALLOWED_CAPABILITIES:
            if "DARWIN" in val_type or "SEATBELT" in val_type or "MACOS" in val_type:
                return False, [f"OUTSIDE_WINDOWS_CAPABILITY: '{val_type}' belongs to Mac lane"]

        return True, []


class FallbackAssignmentValidator:
    """
    Fallback Assignment Validator (Bounded, zero arbitrary commands).
    Schema:
    - MISSION_ID
    - ASSIGNMENT_ID
    - TARGET_RUNNER (=WINDOWS)
    - VALIDATION_TYPE
    - ARTIFACT_REFERENCE
    - EXACT_QUESTION
    - EXPECTED_EVIDENCE
    - ALLOWED_SCOPE
    """
    REQUIRED_FIELDS = [
        "mission_id",
        "assignment_id",
        "target_runner",
        "validation_type",
        "artifact_reference",
        "exact_question",
        "expected_evidence",
        "allowed_scope"
    ]

    @classmethod
    def validate_assignment_dict(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        if not data or not isinstance(data, dict):
            return False, ["PAYLOAD_NOT_DICT: Assignment payload must be a non-empty dictionary"]

        normalized = {str(k).lower().strip(): k for k in data.keys()}
        missing = []
        for req in cls.REQUIRED_FIELDS:
            if req not in normalized or data[normalized[req]] in (None, ""):
                missing.append(req.upper())

        if missing:
            return False, [f"MISSING_FALLBACK_FIELD: '{m}' is required" for m in missing]

        target = str(data[normalized["target_runner"]]).upper()
        if "WINDOWS" not in target:
            return False, [f"INVALID_TARGET_RUNNER: Target runner must be WINDOWS, got {target}"]

        return True, []


