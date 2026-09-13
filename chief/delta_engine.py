"""
delta_engine.py - Chief Multi-Lane Delta & 6-Tier Conflict Resolution Engine
Computes exact state differentials across all agent lanes and reconciles split-brain claims.
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .types import (
    Lane, FindingStatus, FindingSeverity, PatchStatus,
    AuthorityTier, TwoLevelDone, RegisteredFinding, RegisteredPatch
)
from .control_plane import ControlPlane
from .safewrite import safe_write_text, safe_write_json


class ChiefDeltaEngine:
    def __init__(self, control_plane: Optional[ControlPlane] = None):
        self.control_plane = control_plane or ControlPlane()

    def compute_delta(self) -> Dict[str, Any]:
        """
        Computes the complete system delta across findings, patches, tasks, and locks.
        """
        findings = self.control_plane.get_all_findings()
        patches = self.control_plane.get_all_patches()
        tasks = self.control_plane.get_all_tasks()
        locks = self.control_plane.get_active_locks()
        recent_events = self.control_plane.get_recent_events(limit=30)

        # 1. Findings Analysis
        confirmed_findings = [f for f in findings if f.status == FindingStatus.CONFIRMED]
        retracted_findings = [f for f in findings if f.status == FindingStatus.RETRACTED]
        wrong_scope_findings = [f for f in findings if f.status == FindingStatus.WRONG_SCOPE]
        reported_findings = [f for f in findings if f.status == FindingStatus.REPORTED]

        critical_unpatched = [f for f in confirmed_findings if f.severity == FindingSeverity.CRITICAL]

        # 2. Patches Analysis
        proposed_patches = [p for p in patches if p.status == PatchStatus.PROPOSED]
        staged_mac_patches = [p for p in patches if p.status == PatchStatus.STAGED_FOR_MAC]
        verified_patches = [p for p in patches if p.status == PatchStatus.VERIFIED_LOCAL]

        # 3. Tasks & Done Analysis
        all_local_steps_done = all(t.get("local_step_erledigt") == 1 for t in tasks) if tasks else False
        any_gesamtaufgabe_done = any(t.get("gesamtaufgabe_erledigt") == 1 for t in tasks) if tasks else False
        active_blockers = [t["blocker"] for t in tasks if t.get("blocker") not in ("NONE", "", "AWAITING_CHIEF_REQUEST", None)]

        # Two-level company evaluation
        company_local_done = all_local_steps_done
        mac_chief_closed = any(t.get("origin_lane") in ("MAC_GOOGLE", "CHIEF") and t.get("gesamtaufgabe_erledigt") == 1 for t in tasks)
        company_gesamtaufgabe_done = (mac_chief_closed or (any_gesamtaufgabe_done and not any(t.get("blocker") == "AWAITING_CHIEF_REQUEST" for t in tasks))) and (len(active_blockers) == 0) and company_local_done

        # 4. Invalidation & Delegation Guidance
        next_actions = []
        if confirmed_findings and proposed_patches:
            next_actions.append("STAGE_PATCHES_FOR_MAC: Critical vulnerabilities confirmed and patch batches prepared.")
        if any("MAC" in b for b in active_blockers):
            next_actions.append("DISPATCH_TO_MAC_GOOGLE: Windows lab work complete; awaiting Darwin APFS/sandbox verification.")
        if not next_actions:
            next_actions.append("WAITING_FOR_CHIEF_REQUEST: All local tasks completed, awaiting structured request from Mac Chief.")

        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_findings": len(findings),
                "confirmed_count": len(confirmed_findings),
                "retracted_count": len(retracted_findings),
                "wrong_scope_count": len(wrong_scope_findings),
                "reported_count": len(reported_findings),
                "critical_unpatched_count": len(critical_unpatched),
                "total_patches": len(patches),
                "proposed_patches_count": len(proposed_patches),
                "active_tasks_count": len(tasks),
                "active_locks_count": len(locks)
            },
            "two_level_done": {
                "company_local_step_erledigt": company_local_done,
                "company_gesamtaufgabe_erledigt": company_gesamtaufgabe_done,
                "active_blockers": active_blockers
            },
            "findings_by_status": {
                "confirmed": [
                    {"id": f.finding_id, "lane": f.origin_lane.value, "severity": f.severity.value, "desc": f.description}
                    for f in confirmed_findings
                ],
                "retracted": [
                    {"id": f.finding_id, "lane": f.origin_lane.value, "desc": f.description}
                    for f in retracted_findings
                ],
                "wrong_scope": [
                    {"id": f.finding_id, "lane": f.origin_lane.value, "desc": f.description}
                    for f in wrong_scope_findings
                ]
            },
            "patches_breakdown": [
                {"id": p.patch_id, "batch": p.batch_name, "status": p.status.value, "desc": p.description}
                for p in patches
            ],
            "tasks_status": [
                {
                    "assignment_id": t["assignment_id"],
                    "lane": t["origin_lane"],
                    "status": t["status"],
                    "local_done": bool(t["local_step_erledigt"]),
                    "gesamtaufgabe_done": bool(t["gesamtaufgabe_erledigt"]),
                    "blocker": t["blocker"],
                    "next_step": t["next_step"]
                }
                for t in tasks
            ],
            "active_locks": locks,
            "next_recommended_actions": next_actions,
            "recent_events_count": len(recent_events)
        }

    def generate_delta_markdown(self) -> str:
        delta = self.compute_delta()
        s = delta["summary"]
        d = delta["two_level_done"]

        lines = [
            "# COURIER CHIEF — MULTI-LANE DELTA & RECONCILIATION REPORT",
            "",
            f"**Generated UTC**: `{delta['timestamp_utc']}`  ",
            f"**Local Step Erledigt**: `{'JA' if d['company_local_step_erledigt'] else 'NEIN'}`  ",
            f"**Gesamtaufgabe Erledigt**: `{'JA' if d['company_gesamtaufgabe_erledigt'] else 'NEIN'}`  ",
            "",
            "## 1. Executive Metrics",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Total Registered Findings | {s['total_findings']} |",
            f"| Confirmed Vulnerabilities | {s['confirmed_count']} |",
            f"| Retracted Claims | {s['retracted_count']} |",
            f"| Wrong Scope Claims | {s['wrong_scope_count']} |",
            f"| Prepared Patch Batches | {s['total_patches']} |",
            f"| Active Assignments / Tasks | {s['active_tasks_count']} |",
            f"| Active Resource Locks | {s['active_locks_count']} |",
            "",
            "## 2. Reconciled Findings Status",
            ""
        ]

        for status_key, items in delta["findings_by_status"].items():
            lines.append(f"### {status_key.upper()} ({len(items)})")
            if not items:
                lines.append("*(None)*\n")
                continue
            lines.append("| ID | Origin Lane | Severity | Description |")
            lines.append("|---|---|---|---|")
            for it in items:
                lines.append(f"| `{it['id']}` | `{it.get('lane', 'CHIEF')}` | `{it.get('severity', 'INFO')}` | {it.get('desc', '')} |")
            lines.append("")

        lines.extend([
            "## 3. Patch Batches Prepared",
            ""
        ])
        if delta["patches_breakdown"]:
            lines.append("| Patch ID | Batch | Status | Description |")
            lines.append("|---|---|---|---|")
            for p in delta["patches_breakdown"]:
                lines.append(f"| `{p['id']}` | `{p['batch']}` | `{p['status']}` | {p['desc']} |")
            lines.append("")
        else:
            lines.append("*(No patches registered)*\n")

        lines.extend([
            "## 4. Active Blockers & Company State",
            ""
        ])
        if d["active_blockers"]:
            for b in d["active_blockers"]:
                lines.append(f"- **Blocker**: {b}")
        else:
            lines.append("- *(Zero active blockers)*")

        lines.extend([
            "",
            "## 5. Next Recommended Actions",
            ""
        ])
        for act in delta["next_recommended_actions"]:
            lines.append(f"1. **{act}**")
        lines.append("")

        return "\n".join(lines)

    def export_reports(self, output_dir: str = r"C:\Users\lol\2026-workspace\courier-handoffs\windows") -> Dict[str, str]:
        delta_json = self.compute_delta()
        md_text = self.generate_delta_markdown()

        json_path = os.path.join(output_dir, "CHIEF_DELTA_REPORT.json")
        md_path = os.path.join(output_dir, "CHIEF_DELTA_REPORT.md")

        safe_write_json(json_path, delta_json)
        safe_write_text(md_path, md_text)

        return {
            "json_path": json_path,
            "md_path": md_path
        }
