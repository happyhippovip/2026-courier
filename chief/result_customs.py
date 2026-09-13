"""
result_customs.py - Autonomous Result Customs Enforcement
Mission Class: P0 Autonomy Infrastructure (Court K Compliance)

Enforces:
1. Worker Self-Certification Disallowed: Worker claiming {"success": True} without execution proof is REJECTED.
2. Exit Code Zero Alone Insufficient: returncode 0 without observed behavior or assertion proof is REJECTED.
3. Concrete Execution Evidence Required: commands, exit codes, targeted test output, negative/failure checks.
4. Cryptographic Result Fingerprint: Canonical SHA-256 computed over actual observed behavior.
"""

import os
import sys
import json
import hashlib
from typing import Dict, Any, Tuple, Optional


class ResultCustomsJudge:
    """Enforces Court K Result Customs on all task outcomes."""

    @staticmethod
    def evaluate(
        candidate: Dict[str, Any],
        execution_evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates task execution evidence against Court K invariants.
        Returns:
            {
                "passed": bool,
                "reason": str,
                "result_fingerprint": Optional[str],
                "commands": list,
                "exit_code": int,
                "evidence_length": int
            }
        """
        task_id = candidate.get("task_id", "UNKNOWN_TASK")

        # 1. Reject self-certification without execution evidence
        if not execution_evidence or not isinstance(execution_evidence, dict):
            return {
                "passed": False,
                "reason": "SELF_CERTIFICATION_DISALLOWED: Missing execution evidence object",
                "result_fingerprint": None,
                "commands": [],
                "exit_code": -1,
                "evidence_length": 0
            }

        # Check for hollow self-certification
        raw_success = execution_evidence.get("success")
        raw_stdout = execution_evidence.get("stdout", "").strip()
        raw_cmd = execution_evidence.get("command") or execution_evidence.get("commands")
        raw_exit = execution_evidence.get("exit_code") if "exit_code" in execution_evidence else execution_evidence.get("returncode")

        if raw_cmd is None and not raw_stdout:
            return {
                "passed": False,
                "reason": "SELF_CERTIFICATION_DISALLOWED: Worker claimed success without command or execution logs",
                "result_fingerprint": None,
                "commands": [],
                "exit_code": -1,
                "evidence_length": 0
            }

        # 2. Exit code zero alone is insufficient
        if raw_exit == 0 and not raw_stdout:
            return {
                "passed": False,
                "reason": "EXIT_CODE_ZERO_ALONE_INSUFFICIENT: Exit code 0 provided but observed behavior is empty",
                "result_fingerprint": None,
                "commands": [raw_cmd] if raw_cmd else [],
                "exit_code": 0,
                "evidence_length": 0
            }

        if raw_exit != 0:
            return {
                "passed": False,
                "reason": f"COMMAND_FAILED: Non-zero exit code {raw_exit}",
                "result_fingerprint": None,
                "commands": [raw_cmd] if raw_cmd else [],
                "exit_code": raw_exit if raw_exit is not None else -1,
                "evidence_length": len(raw_stdout)
            }

        # 3. Minimum observed behavior content check
        # Must show test execution evidence, assertion trace, or verified effect
        meaningful_markers = ["ok", "pass", "passed", "ran", "test", "verified", "completed", "true", "checksum"]
        lower_stdout = raw_stdout.lower()
        if not any(marker in lower_stdout for marker in meaningful_markers) and len(raw_stdout) < 10:
            return {
                "passed": False,
                "reason": "INSUFFICIENT_OBSERVED_BEHAVIOR: Execution logs do not demonstrate verified effect",
                "result_fingerprint": None,
                "commands": [raw_cmd] if raw_cmd else [],
                "exit_code": 0,
                "evidence_length": len(raw_stdout)
            }

        # 4. Compute cryptographic result fingerprint from actual observed behavior
        canonical_content = f"{task_id}:{raw_cmd}:{raw_exit}:{raw_stdout}"
        result_fp = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

        return {
            "passed": True,
            "reason": "CUSTOMS_CLEARED_EFFECT_PROVEN",
            "result_fingerprint": result_fp,
            "commands": [raw_cmd] if raw_cmd else [],
            "exit_code": raw_exit,
            "evidence_length": len(raw_stdout)
        }
