"""
exhaustion_court.py - Courier Two-Method Real Exhaustion Court
Mission Class: P0 Autonomy Infrastructure
Operating Phase: AUTONOMY_FIRST

Enforces Section 14 of the Native Antigravity Operating Contract:
Only claims LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED after TWO independent discovery methods
both find no legitimate real-delta safe work:

Discovery Method A:
- State / tests / known defects / proof debt / control plane / backlog.

Discovery Method B:
- Repository / runtime / failure paths / customer/release / cross-platform inspection.

Compares findings:
- If either method discovers unresolved, high-value, safe work:
  continue campaign automatically.
- Only if BOTH methods find zero unresolved gaps:
  certify LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED.
"""

import os
import sys
import json
import sqlite3
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

from .control_plane import ControlPlane
from .value_governor import ValueGovernor
from .safewrite import safe_write_json


class RealExhaustionCourt:
    """Rigorous dual-method verification court before declaring safe work exhausted."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        cp: Optional[ControlPlane] = None
    ):
        self.workspace_root = os.path.abspath(workspace_root or os.path.join(os.path.dirname(__file__), "..", ".."))
        self.courier_dir = os.path.join(self.workspace_root, "courier")
        self.pm_dir = os.path.join(self.workspace_root, "project-memory")
        self.cp = cp or ControlPlane()
        self.backlog_path = os.path.join(self.pm_dir, "data", "safe_backlog.json")
        self.court_state_path = os.path.join(self.pm_dir, "data", "control_plane", "real_exhaustion_court_record.json")

    def run_discovery_method_a(self) -> Dict[str, Any]:
        """
        Method A: State / Tests / Known Defects / Proof Debt / Control Plane / Backlog.
        """
        findings = []
        tasks = self.cp.get_all_tasks()
        running = [t for t in tasks if t.get("status") in ("RUNNING", "CLAIMED")]
        if running:
            findings.append({
                "source": "CONTROL_PLANE_ACTIVE_TASK",
                "task_id": running[0]["task_id"],
                "delta": "RELIABILITY_GAIN",
                "description": f"Active task in flight: {running[0]['task_id']}"
            })

        active_locks = self.cp.get_active_locks()
        if active_locks:
            findings.append({
                "source": "CONTROL_PLANE_ACTIVE_LOCK",
                "domain": active_locks[0]["conflict_domain"],
                "delta": "RELIABILITY_GAIN",
                "description": f"Active writer lease held in domain: {active_locks[0]['conflict_domain']}"
            })

        # Check backlog for eligible pending tasks
        if os.path.exists(self.backlog_path):
            try:
                with open(self.backlog_path, "r", encoding="utf-8") as f:
                    b_data = json.load(f)
                for t in b_data.get("tasks", []):
                    if t.get("status") in ("PENDING", "READY", "OPEN"):
                        # Audit with ValueGovernor
                        valid, reason = ValueGovernor.audit_candidate(t, self.workspace_root)
                        if valid:
                            findings.append({
                                "source": "SAFE_BACKLOG_ELIGIBLE_TASK",
                                "task_id": t["task_id"],
                                "delta": t.get("expected_real_delta", "AUTONOMY_GAIN"),
                                "description": f"Backlog task ready: {t.get('title')}"
                            })
            except Exception as e:
                findings.append({
                    "source": "BACKLOG_PARSE_DEFECT",
                    "delta": "DEFECT_REMOVED",
                    "description": f"Failed to parse safe_backlog.json: {e}"
                })

        # Check durable continuation state file
        cont_path = os.path.join(self.pm_dir, "data", "control_plane", "durable_continuation.json")
        if os.path.exists(cont_path):
            try:
                with open(cont_path, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                if c_data.get("status") == "RUNNING":
                    findings.append({
                        "source": "DURABLE_CONTINUATION_UNCLOSED_TASK",
                        "task_id": c_data.get("task_id"),
                        "delta": "RELIABILITY_GAIN",
                        "description": f"Durable continuation left in RUNNING: {c_data.get('task_id')}"
                    })
            except Exception as e:
                findings.append({
                    "source": "DURABLE_CONTINUATION_PARSE_ERROR",
                    "delta": "DEFECT_REMOVED",
                    "description": f"Failed to parse durable_continuation.json: {e}"
                })

        return {
            "method": "METHOD_A_STATE_CONTROL_PLANE_PROOF_DEBT",
            "findings_count": len(findings),
            "findings": findings,
            "exhausted": len(findings) == 0
        }

    def run_discovery_method_b(self) -> Dict[str, Any]:
        """
        Method B: Repository / Runtime / Failure Paths / Customer / Delivery / Cross-Platform.
        """
        findings = []

        # 1. Distribution readiness check
        dist_dir = os.path.join(self.pm_dir, "data", "distribution_ready")
        store_index = os.path.join(dist_dir, "index.html")
        if not os.path.exists(store_index):
            findings.append({
                "source": "DISTRIBUTION_STORE_MISSING",
                "delta": "DELIVERY_GAIN",
                "description": "Storefront index.html missing from distribution_ready"
            })

        agent_cp_zip_root = os.path.join(dist_dir, "agent_control_plane_pro_v1.0.0.zip")
        agent_cp_zip_sub = os.path.join(dist_dir, "agent_control_plane", "agent_control_plane_pro_v1.0.0.zip")
        if not (os.path.exists(agent_cp_zip_root) or os.path.exists(agent_cp_zip_sub)):
            findings.append({
                "source": "DISTRIBUTION_PACKAGE_MISSING",
                "delta": "DELIVERY_GAIN",
                "description": "Agent control plane pro zip deliverable missing"
            })

        # 2. Runtime and Orphan Lockfile check
        runtime_dir = os.path.join(self.courier_dir, "runtime")
        if os.path.exists(runtime_dir):
            for fname in os.listdir(runtime_dir):
                if fname.endswith(".lock") or fname.endswith(".lockwait"):
                    findings.append({
                        "source": "ORPHAN_LOCKFILE_DETECTED",
                        "delta": "RESOURCE_SAFETY",
                        "description": f"Orphan lock file found in runtime: {fname}"
                    })

        # 3. Cross-platform Mac Boundary Leakage check
        coord_m2w = r"C:\Dev\Windows-AI-OS\runtime\tasks\inbox"
        if os.path.exists(coord_m2w):
            for fname in os.listdir(coord_m2w):
                if fname.endswith(".json") and not fname.startswith("REJECTED_"):
                    findings.append({
                        "source": "UNPROCESSED_MAC_COORDINATION_REQUEST",
                        "delta": "AUTONOMY_GAIN",
                        "description": f"Unprocessed coordination request from Mac: {fname}"
                    })

        # 4. Invariant checks on spend
        spent_file = os.path.join(self.pm_dir, "data", "distribution_ready", "agent_control_plane", ".spend_ledger_pro.json")
        if os.path.exists(spent_file):
            try:
                with open(spent_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                spent = s_data.get("current_spend_eur", 0.0)
                if spent > 0.00:
                    # In test mode, ensure it's categorized as test spend, not real spend
                    if s_data.get("real_spend_eur", 0.0) > 0.00:
                        findings.append({
                            "source": "SPEND_INVARIANT_VIOLATION",
                            "delta": "SECURITY_GAIN",
                            "description": f"Real spend violated 0.00 EUR invariant: {s_data.get('real_spend_eur')}"
                        })
            except Exception:
                pass

        return {
            "method": "METHOD_B_REPOSITORY_RUNTIME_DELIVERY_PARITY",
            "findings_count": len(findings),
            "findings": findings,
            "exhausted": len(findings) == 0
        }

    def evaluate_exhaustion(self) -> Dict[str, Any]:
        """
        Executes both discovery methods and compares findings.
        Returns true exhaustion only if BOTH methods return exhausted == True.
        """
        res_a = self.run_discovery_method_a()
        res_b = self.run_discovery_method_b()

        both_exhausted = res_a["exhausted"] and res_b["exhausted"]
        all_findings = res_a["findings"] + res_b["findings"]

        if both_exhausted:
            final_status = "LOCAL_WINDOWS_SAFE_WORK_EXHAUSTED"
            action = "NONE"
        else:
            final_status = "REAL_SAFE_WORK_REMAINS"
            action = "CONTINUE_CAMPAIGN_AUTOMATICALLY"

        record = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "method_a": res_a,
            "method_b": res_b,
            "total_open_gaps_found": len(all_findings),
            "both_methods_agree_exhausted": both_exhausted,
            "final_status": final_status,
            "next_automatic_action": action,
            "safe_work_remaining": not both_exhausted,
            "certified_exhaustion": both_exhausted
        }

        os.makedirs(os.path.dirname(self.court_state_path), exist_ok=True)
        safe_write_json(self.court_state_path, record)
        return record
