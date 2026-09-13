"""
value_governor.py - Courier Value Governor and Anti-Busywork Court
Mission Class: P0 Autonomy Infrastructure
Operating Phase: AUTONOMY_FIRST

Enforces:
1. No Task-Count Inflation / Milestone Theater
2. No Speculative Overengineering without Measured Need
3. No Generic Acceptance Court Reuse as Substitute for Task Proof
4. Strict Source Evidence and Measurable Real Delta Requirements
5. Accurate Arithmetic Reconciliation between Control Plane and Safe Backlog
"""

import os
import sys
import re
import json
import sqlite3
from typing import Dict, Any, List, Tuple, Optional, Set

ALLOWED_REAL_DELTAS = {
    "CAPABILITY_GAIN",
    "DEFECT_REMOVAL",
    "UNCERTAINTY_REDUCTION",
    "PROOF_DEBT_REDUCTION",
    "AUTONOMY_GAIN",
    "RELIABILITY_GAIN",
    "SECURITY_GAIN",
    "PERFORMANCE_GAIN",
    "COST_REDUCTION",
    "CUSTOMER_VALUE_GAIN",
    "DELIVERY_GAIN",
    "RESOURCE_SAFETY",
    "ACCESSIBILITY_GAIN"
}

MILESTONE_PATTERNS = [
    "milestone", "symphony proof", "task proof", "reserve proof",
    "task count", "centennial", "millennial", "symphony master",
    "symphony autonomous reserve proof", "autonomous reserve proof",
    "proof of "
]

SPECULATIVE_PATTERNS = [
    "saml", "iso 20022", "iso20022", "camt.053", "pacs.008", "epc qr",
    "merkle", "brotli", "microsecond", "zero-copy", "floating license",
    "caiq", "rfp simulator", "whitepaper builder", "pain.001"
]

GENERIC_TEST_SUITES = {
    "courier/tests/test_permanent_reserve_acceptance_court.py",
    "courier/tests/test_windows_100_acceptance_court.py"
}


class ValueGovernor:
    """Enforces strict value selection and rejects cosmetic or speculative task generation."""

    @staticmethod
    def audit_candidate(candidate: Dict[str, Any], workspace_root: Optional[str] = None) -> Tuple[bool, str]:
        root = workspace_root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        title = str(candidate.get("title", "")).lower()

        # 1. Milestone Theater Check
        for pat in MILESTONE_PATTERNS:
            if pat in title:
                return False, f"REJECTED_MILESTONE_THEATER: title contains '{pat}'"

        # 2. Speculative Overengineering Check
        domain = str(candidate.get("conflict_scope", "")).lower()
        for spec in SPECULATIVE_PATTERNS:
            if spec in title or spec in domain:
                return False, f"REJECTED_SPECULATIVE_OVERENGINEERING: matches pattern '{spec}' without current measured gap"

        # 3. Busywork / Churn Check
        busywork_patterns = [
            "status-report", "status report", "readme churn", "percentage churn",
            "duplicate architecture", "fake benchmark", "duplicate test",
            "renaming-only", "task count inflation", "repeating verified", "churn"
        ]
        for bw in busywork_patterns:
            if bw in title:
                return False, f"REJECTED_BUSYWORK_DETECTED: '{bw}' in title"

        # Check for repetitive test/benchmark rounds
        if re.search(r"\bround\s+\d+\b", title, re.IGNORECASE):
            return False, "REJECTED_REPETITIVE_TEST_ROUND: repetitive test execution without code diff"

        # 4. Real Delta Requirement
        delta = candidate.get("expected_real_delta")
        if not delta or delta not in ALLOWED_REAL_DELTAS:
            return False, f"REJECTED_INVALID_DELTA: '{delta}' not in ALLOWED_REAL_DELTAS"

        # 5. Source Evidence Requirement
        source = candidate.get("source_evidence")
        if not source or source == "NONE":
            return False, "REJECTED_MISSING_SOURCE_EVIDENCE: source_evidence is NONE"
        full_source = os.path.join(root, source) if not os.path.isabs(source) else source
        if not os.path.exists(full_source):
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            fallback_source = os.path.join(repo_root, source)
            if os.path.exists(fallback_source):
                full_source = fallback_source
            else:
                return False, f"REJECTED_SOURCE_EVIDENCE_NOT_FOUND: '{source}' does not exist on disk"

        # 6. Distinct Verification Requirement (Anti-Generic-Court Reuse)
        script = candidate.get("script_path")
        if not script or script == "NONE":
            return False, "REJECTED_MISSING_VERIFICATION_SCRIPT: script_path is NONE"
        
        normalized_script = script.replace("\\", "/")
        if normalized_script in GENERIC_TEST_SUITES:
            return False, f"REJECTED_GENERIC_COURT_REUSE: candidate cannot reuse '{normalized_script}' as substitute for task proof"

        full_script = os.path.join(root, script) if not os.path.isabs(script) else script
        if not os.path.exists(full_script):
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            fallback_script = os.path.join(repo_root, script)
            if os.path.exists(fallback_script):
                full_script = fallback_script
            else:
                return False, f"REJECTED_VERIFICATION_SCRIPT_NOT_FOUND: '{script}' does not exist on disk"

        return True, "ACCEPTED"

    @staticmethod
    def reconcile_arithmetic(cp_db_path: str, backlog_path: str) -> Dict[str, Any]:
        conn = sqlite3.connect(cp_db_path)
        cur = conn.cursor()
        cur.execute("SELECT task_id, status FROM tasks WHERE status='COMPLETED'")
        all_completed = cur.fetchall()
        conn.close()

        historical_fallback = []
        timestamped_test = []
        legitimate_win = []
        for r in all_completed:
            tid = r[0]
            if not tid.startswith("TASK-WIN-"):
                historical_fallback.append(tid)
            elif re.match(r"^TASK-WIN-\d{10}", tid) or "TEST" in tid:
                timestamped_test.append(tid)
            else:
                legitimate_win.append(tid)

        sb_completed = []
        if os.path.exists(backlog_path):
            with open(backlog_path, "r", encoding="utf-8") as f:
                sb_data = json.load(f)
            sb_completed = [t["task_id"] for t in sb_data.get("tasks", []) if t.get("status") == "COMPLETED"]

        return {
            "cp_total_completed_rows": len(all_completed),
            "cp_historical_fallback_count": len(historical_fallback),
            "cp_timestamped_test_count": len(timestamped_test),
            "cp_legitimate_win_count": len(legitimate_win),
            "safe_backlog_completed_count": len(sb_completed),
            "historical_fallback_ids": historical_fallback[:10],
            "timestamped_test_ids": timestamped_test[:10]
        }
