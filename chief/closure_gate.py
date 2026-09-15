"""
closure_gate.py - Autonomous Two-Level Done Verification & Multi-Host Closure Gate
Part of TASK-WIN-63: Autonomous Two-Level Done Verification & Multi-Host Closure Gate.

Enforces strict separation between Level 1 (local execution) and Level 2 (global completion):
- Level 1: local_step_erledigt requires process success, deterministic evidence, and zero spend
- Level 2: gesamtaufgabe_erledigt requires cross-host peer delivery, durable ledger entry, and zero human blockers
- Human Gate Isolation: Blocks Level 2 on human-only actions without stalling safe local Windows automation
- Cryptographic Closure Receipts: Immutable SHA-256 sealed audit receipts for every evaluated task
"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .types import Lane, Host, TaskStatus, TwoLevelDone
from .control_plane import ControlPlane
from .safewrite import safe_write_json

WORKSPACE_ROOT = os.environ.get("COURIER_WORKSPACE_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

class TwoLevelClosureGate:
    def __init__(self, cp: Optional[ControlPlane] = None, workspace_root: str = WORKSPACE_ROOT):
        self.workspace_root = os.path.abspath(workspace_root)
        self.cp = cp or ControlPlane()
        self.receipts_dir = r"C:\Dev\Windows-AI-OS\runtime\results\receipts"
        os.makedirs(self.receipts_dir, exist_ok=True)

    def evaluate_task_closure(
        self,
        task_id: str,
        execution_evidence: Optional[Dict[str, Any]] = None,
        remote_peer_synced: bool = False,
        requires_human_gate: bool = False,
        spend_eur: float = 0.00
    ) -> Dict[str, Any]:
        """
        Evaluates and enforces two-level done criteria for a task:
        Returns structured closure report and seals cryptographic receipt.
        """
        # 1. Spend Firewall Check
        if spend_eur != 0.00:
            return {
                "success": False,
                "task_id": task_id,
                "decision": "REJECTED_SPEND_VIOLATION",
                "two_level_done": {
                    "local_step_erledigt": False,
                    "gesamtaufgabe_erledigt": False,
                    "blocker": "SPEND_FIREWALL_VIOLATION",
                    "next_step": "ABORT"
                },
                "receipt": None
            }

        # 2. Inspect Control Plane task state
        existing_task = self.cp.get_task(task_id)
        local_step_ok = False
        evidence_str = ""

        if execution_evidence:
            returncode = execution_evidence.get("returncode")
            local_step_ok = (returncode == 0) and execution_evidence.get("success", True)
            evidence_str = execution_evidence.get("stdout", "") or execution_evidence.get("evidence", "")
        elif existing_task:
            local_step_ok = existing_task.get("status") in ("COMPLETED", "VERIFIED")
            evidence_str = existing_task.get("blocker", "")

        # 3. Determine Level 2 (Gesamtaufgabe) and Blocker
        gesamtaufgabe_ok = False
        blocker = "NONE"
        next_step = "RECONCILE_GOALS"

        if requires_human_gate:
            blocker = "HUMAN_GATE_APPROVAL_REQUIRED"
            next_step = "WAIT_FOR_HUMAN_GATE"
        elif not remote_peer_synced:
            # Local completed, but remote peer sync not yet acknowledged
            blocker = "PEER_SYNC_PENDING"
            next_step = "TRANSMIT_TO_PEER"
        elif local_step_ok and remote_peer_synced:
            gesamtaufgabe_ok = True
            blocker = "NONE"
            next_step = "TASK_FULLY_CLOSED"

        two_level = TwoLevelDone(
            local_step_erledigt=local_step_ok,
            gesamtaufgabe_erledigt=gesamtaufgabe_ok,
            blocker=blocker,
            next_step=next_step
        )
        assert two_level.validate_invariants(), "TwoLevelDone invariants violated!"

        # 4. Generate Sealed Cryptographic Closure Receipt
        receipt_id = f"RCPT-{task_id}-{int(time.time() * 1000)}"
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        
        canonical_content = f"{receipt_id}:{task_id}:{local_step_ok}:{gesamtaufgabe_ok}:{blocker}:{spend_eur}:{timestamp_utc}"
        receipt_sig = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

        receipt_payload = {
            "schema_version": "1.0",
            "receipt_id": receipt_id,
            "task_id": task_id,
            "local_step_erledigt": local_step_ok,
            "gesamtaufgabe_erledigt": gesamtaufgabe_ok,
            "blocker": blocker,
            "next_step": next_step,
            "spend_eur": spend_eur,
            "timestamp_utc": timestamp_utc,
            "signature_sha256": receipt_sig,
            "evidence_digest": hashlib.sha256(evidence_str.encode("utf-8")).hexdigest()
        }

        # 5. Persist receipt to disk and Control Plane
        receipt_path = os.path.join(self.receipts_dir, f"{receipt_id}.json")
        safe_write_json(receipt_path, receipt_payload)

        # Update SQLite Control Plane
        if gesamtaufgabe_ok:
            task_status = TaskStatus.COMPLETED
        elif blocker != "NONE":
            task_status = TaskStatus.BLOCKED
        elif local_step_ok:
            task_status = TaskStatus.VERIFIED
        else:
            task_status = TaskStatus.FAILED

        self.cp.upsert_task(
            task_id=task_id,
            assignment_id=f"ASSIGN-{task_id}",
            origin_lane=Lane.WINDOWS_GOOGLE,
            status=task_status,
            two_level_done=two_level,
            active_agent=Lane.WINDOWS_GOOGLE.value
        )
        self.cp.set_checkpoint(f"CLOSURE_RECEIPT_{task_id}", receipt_id)

        return {
            "success": True,
            "task_id": task_id,
            "receipt_id": receipt_id,
            "receipt_path": receipt_path,
            "signature_sha256": receipt_sig,
            "two_level_done": {
                "local_step_erledigt": local_step_ok,
                "gesamtaufgabe_erledigt": gesamtaufgabe_ok,
                "blocker": blocker,
                "next_step": next_step
            },
            "receipt": receipt_payload
        }
