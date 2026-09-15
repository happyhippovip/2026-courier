"""
ingestor.py - Automated Local Chief Ingestion Engine
Continuously ingests, validates, and cataloges handoffs from all agent lanes.
"""

import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .types import (
    Lane, Host, TaskStatus, FindingStatus, FindingSeverity,
    PatchStatus, IngestedHandoff, TwoLevelDone
)
from .control_plane import ControlPlane, DEFAULT_DB_PATH
from .validator import HandoffValidator


DEFAULT_HANDOFFS_DIR = os.environ.get("COURIER_HANDOFFS_DIR") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "courier-handoffs", "windows")
)


class ChiefIngestor:
    def __init__(
        self,
        control_plane: Optional[ControlPlane] = None,
        handoffs_dir: str = DEFAULT_HANDOFFS_DIR,
        cp: Optional[ControlPlane] = None
    ):
        self.control_plane = control_plane or cp or ControlPlane()
        self.handoffs_dir = os.path.abspath(handoffs_dir)

    def compute_sha256(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def ingest_file(self, filepath: str) -> Dict[str, Any]:
        filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath):
            return {"success": False, "error": f"File not found: {filepath}", "status": "NOT_FOUND"}

        # Only JSON or MD files
        if not filepath.endswith(".json") and not filepath.endswith(".md"):
            return {"success": False, "error": "Unsupported file format (must be .json or .md)", "status": "IGNORED"}

        # For MD files, we note them or parse if needed, but primary structured payload is JSON
        if filepath.endswith(".md"):
            return {"success": True, "status": "MD_COMPANION_ACKNOWLEDGED", "filepath": filepath}

        # Inbound requests and dispatch envelopes are handled by the coordinator/resolver
        base_name = os.path.basename(filepath)
        if base_name.startswith("REQUEST_") or base_name.startswith("DISPATCH_") or base_name.startswith("ASSIGN_") or base_name.startswith("RESULT_"):
            return {"success": True, "status": "REQUEST_ENVELOPE_RESERVED", "filepath": filepath}

        sha256_hash = self.compute_sha256(filepath)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            return {
                "success": False,
                "error": f"Malformed JSON: {e}",
                "status": "REJECTED_MALFORMED",
                "sha256_hash": sha256_hash,
                "filepath": filepath
            }

        # Validate payload
        is_valid, validation_errors = HandoffValidator.validate_handoff_payload(payload, filepath)
        if not is_valid:
            return {
                "success": False,
                "error": "Validation failed: " + "; ".join(validation_errors),
                "status": "REJECTED_VALIDATION",
                "validation_errors": validation_errors,
                "sha256_hash": sha256_hash,
                "filepath": filepath
            }

        origin_lane = Lane.from_str(payload.get("origin", "UNKNOWN"))
        assignment_id = payload.get("assignment_id", "UNKNOWN")
        role = payload.get("role", "UNKNOWN")
        timestamp_utc = payload.get("timestamp_utc", datetime.now(timezone.utc).isoformat())
        host_os = Host.from_str(payload.get("host_os", "UNKNOWN"))
        mac_host_access = bool(payload.get("mac_host_access", False))
        prod_write_auth = bool(payload.get("production_write_authority", False))

        handoff_id = f"HND-{origin_lane.value}-{os.path.basename(filepath)}"

        # 1. Record Handoff into SQLite Control Plane
        recorded = self.control_plane.record_handoff(
            handoff_id=handoff_id,
            source_file=filepath,
            origin_lane=origin_lane,
            assignment_id=assignment_id,
            role=role,
            timestamp_utc=timestamp_utc,
            host_os=host_os,
            mac_host_access=mac_host_access,
            production_write_authority=prod_write_auth,
            sha256_hash=sha256_hash,
            payload=payload,
            validation_status="VERIFIED"
        )

        if not recorded:
            return {
                "success": True,
                "status": "SKIPPED_ALREADY_INGESTED",
                "handoff_id": handoff_id,
                "sha256_hash": sha256_hash,
                "filepath": filepath
            }

        # 2. Extract & Upsert Findings
        findings_count = self._extract_findings(payload, origin_lane)

        # 3. Extract & Upsert Patches
        patches_count = self._extract_patches(payload)

        # 4. Extract & Upsert Canonical Task
        self._extract_task(payload, origin_lane, assignment_id)

        return {
            "success": True,
            "status": "INGESTED",
            "handoff_id": handoff_id,
            "sha256_hash": sha256_hash,
            "filepath": filepath,
            "origin_lane": origin_lane.value,
            "assignment_id": assignment_id,
            "findings_registered": findings_count,
            "patches_registered": patches_count
        }

    def _extract_findings(self, payload: Dict[str, Any], origin_lane: Lane) -> int:
        count = 0
        # Check confirmed_findings, retracted_findings, wrong_scope_findings
        confirmed_set = set(payload.get("confirmed_findings", []))
        retracted_set = set(payload.get("retracted_findings", []))
        wrong_scope_set = set(payload.get("wrong_scope_findings", []))

        # Check new_findings list (can be strings or dicts)
        new_findings = payload.get("new_findings", [])
        for item in new_findings:
            if isinstance(item, str):
                parts = item.split(":", 1)
                f_id = parts[0].strip()
                desc = parts[1].strip() if len(parts) > 1 else ""
                title = f_id
            elif isinstance(item, dict):
                f_id = item.get("id", item.get("finding_id", "UNKNOWN"))
                title = item.get("title", f_id)
                desc = item.get("description", "")
            else:
                continue

            # Determine status
            status = FindingStatus.REPORTED
            if any(f_id in s for s in confirmed_set):
                status = FindingStatus.CONFIRMED
            elif any(f_id in s for s in retracted_set):
                status = FindingStatus.RETRACTED
            elif any(f_id in s for s in wrong_scope_set):
                status = FindingStatus.WRONG_SCOPE

            severity = FindingSeverity.HIGH
            if "CRITICAL" in desc.upper():
                severity = FindingSeverity.CRITICAL
            elif "MEDIUM" in desc.upper():
                severity = FindingSeverity.MEDIUM
            elif "LOW" in desc.upper():
                severity = FindingSeverity.LOW

            self.control_plane.upsert_finding(
                finding_id=f_id,
                origin_lane=origin_lane,
                title=title,
                status=status,
                severity=severity,
                description=desc
            )
            count += 1

        # Also register any confirmed items that weren't in new_findings
        for c in confirmed_set:
            f_id = c.split(":")[0].strip()
            self.control_plane.upsert_finding(
                finding_id=f_id,
                origin_lane=origin_lane,
                title=f_id,
                status=FindingStatus.CONFIRMED,
                severity=FindingSeverity.HIGH,
                description=f"Confirmed in {payload.get('assignment_id', 'UNKNOWN')}"
            )
            count += 1

        for r in retracted_set:
            f_id = r.split(":")[0].strip()
            self.control_plane.upsert_finding(
                finding_id=f_id,
                origin_lane=origin_lane,
                title=f_id,
                status=FindingStatus.RETRACTED,
                severity=FindingSeverity.LOW,
                description=r
            )
            count += 1

        return count

    def _extract_patches(self, payload: Dict[str, Any]) -> int:
        count = 0
        patch_batches = payload.get("patch_batches", [])
        for p in patch_batches:
            if isinstance(p, str):
                parts = p.split("(", 1)
                batch_name = parts[0].strip()
                desc = parts[1].rstrip(")") if len(parts) > 1 else ""
                patch_id = f"PATCH-{batch_name}"
                self.control_plane.upsert_patch(
                    patch_id=patch_id,
                    batch_name=batch_name,
                    status=PatchStatus.PROPOSED,
                    description=desc,
                    target_files=[],
                    reproduction_scripts=[]
                )
                count += 1
            elif isinstance(p, dict):
                patch_id = p.get("id", p.get("patch_id", f"PATCH-{count}"))
                self.control_plane.upsert_patch(
                    patch_id=patch_id,
                    batch_name=p.get("batch_name", patch_id),
                    status=PatchStatus.PROPOSED,
                    description=p.get("description", ""),
                    target_files=p.get("target_files", []),
                    reproduction_scripts=p.get("reproduction_scripts", [])
                )
                count += 1
        return count

    def _extract_task(self, payload: Dict[str, Any], origin_lane: Lane, assignment_id: str):
        task_id = payload.get("windows_validation_request_id") or payload.get("task_id")
        if not task_id:
            task_id = assignment_id if str(assignment_id).startswith("TASK-") else f"TASK-{assignment_id}"

        existing_task = self.control_plane.get_task(task_id)
        if not existing_task:
            all_tasks = self.control_plane.get_all_tasks()
            existing_task = next((t for t in all_tasks if t.get("assignment_id") == assignment_id), None)
            
        if existing_task and existing_task.get("status") in ("COMPLETED", "VERIFIED", "FAILED", "REJECTED"):
            return

        two_level = payload.get("two_level_done") or {}

        # Check for explicit two_level_done block first
        if "local_step_erledigt" in two_level:
            local_step_done = bool(two_level.get("local_step_erledigt", True))
            gesamtaufgabe_done = bool(two_level.get("gesamtaufgabe_erledigt", True))
            blocker = str(two_level.get("blocker", "NONE"))
            next_task = str(two_level.get("next_step", "CONTINUE_COORDINATION"))
        else:
            # Check for mac / codex dependencies
            mac_deps = payload.get("mac_dependencies", [])
            codex_deps = payload.get("codex_dependencies", [])
            if mac_deps or codex_deps:
                local_step_done = True
                gesamtaufgabe_done = False
                blocker = f"GATED_ON_MAC_CODEX ({len(mac_deps)} Mac deps, {len(codex_deps)} Codex deps)"
            else:
                local_step_done = bool(payload.get("local_step_erledigt", True))
                gesamtaufgabe_done = bool(payload.get("gesamtaufgabe_erledigt", True))
                blocker = str(payload.get("blocker", "NONE"))
            next_task = payload.get("next_independent_task", "CONTINUE_COORDINATION")

        is_completed = local_step_done and (blocker in ("NONE", "", "AWAITING_CHIEF_REQUEST") or not blocker)

        import hashlib
        fp_str = f"{task_id}:{assignment_id}:{local_step_done}:{gesamtaufgabe_done}:{blocker}:{next_task}"
        canonical_fingerprint = hashlib.sha256(fp_str.encode('utf-8')).hexdigest()

        self.control_plane.upsert_task(
            task_id=task_id,
            assignment_id=assignment_id,
            origin_lane=origin_lane,
            status=TaskStatus.COMPLETED if is_completed else TaskStatus.RUNNING,
            two_level_done=TwoLevelDone(
                local_step_erledigt=local_step_done,
                gesamtaufgabe_erledigt=gesamtaufgabe_done,
                blocker=blocker,
                next_step=next_task
            ),
            active_agent=origin_lane.value,
            canonical_fingerprint=canonical_fingerprint
        )

    def scan_and_ingest(self, target_dir: Optional[str] = None) -> Dict[str, Any]:
        dir_to_scan = os.path.abspath(target_dir or self.handoffs_dir)
        if not os.path.exists(dir_to_scan):
            return {"total_scanned": 0, "ingested": [], "skipped": [], "rejected": [], "error": f"Dir not found: {dir_to_scan}"}

        ingested = []
        skipped = []
        rejected = []

        for root, _, files in os.walk(dir_to_scan):
            for filename in files:
                if filename.endswith(".json"):
                    full_path = os.path.join(root, filename)
                    res = self.ingest_file(full_path)
                    if res.get("status") == "INGESTED":
                        ingested.append(res)
                    elif res.get("status") == "SKIPPED_ALREADY_INGESTED":
                        skipped.append(res)
                    else:
                        rejected.append(res)

        return {
            "total_scanned": len(ingested) + len(skipped) + len(rejected),
            "ingested_count": len(ingested),
            "skipped_count": len(skipped),
            "rejected_count": len(rejected),
            "ingested": ingested,
            "skipped": skipped,
            "rejected": rejected
        }
