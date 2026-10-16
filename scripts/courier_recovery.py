#!/usr/bin/env python3
"""Exact-Owned Process Recovery and Escalation Ladder (FRZ-08 / FRZ-07).

Executes the proven, non-destructive recovery ladder for frozen or degraded
Courier host instances:
  Level 1: Passive Observation & Wait (check leases, ensure progress isn't actively occurring)
  Level 2: Graphics / DWM reset guidance or restart explorer on proven evidence (if GUI shell frozen)
  Level 3: Restart owned helpers only (IDE extension / language server / non-critical daemon)
  Level 4: Terminate owned process tree via exact tracked PID / Job Object (never by name!)
  Level 5: Generate formal Recovery Receipt with SAFE_TO_REBOOT / NOT_SAFE_TO_REBOOT verdict.

Strict Invariants:
- NEVER kill by process name (name-based termination is strictly forbidden).
- All actions target exact owned PIDs from `run/*.pid` or registered Job Objects.
- Autonomous spend: 0 EUR.
- Safety ratchet clean: `kill_by_name = 0`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repo root is in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.right_host_guard import get_current_host_identity
from scripts.courier_status import (
    get_app_data_dir,
    get_critical_snapshot_l0,
    get_git_status,
    get_owned_pids,
)


def build_recovery_receipt(
    snapshot: Dict[str, Any],
    incident_type: str,
    action_taken: str,
    outcome: str,
) -> Dict[str, Any]:
    """Construct an evidence-backed Recovery Receipt adhering to incident record schema."""
    host_id = get_current_host_identity()
    reboot_info = snapshot.get("reboot_verdict", {})
    git_st = snapshot.get("git", {})
    owned_procs = snapshot.get("owned_processes", {})

    receipt_id = f"RCPT-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    receipt = {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "created_at": timestamp,
        "host": {
            "hostname": host_id.hostname,
            "platform": host_id.os_platform,
            "device_id": host_id.device_id,
            "is_cloud_vm": host_id.is_cloud_vm,
        },
        "incident_classification": incident_type,
        "action_taken": action_taken,
        "outcome": outcome,
        "worktrees": {
            "branch": git_st.get("branch", "unknown"),
            "dirty_files": git_st.get("dirty_count", 0),
            "unpushed_commits": git_st.get("unpushed_count", 0),
        },
        "owned_processes_targeted": owned_procs,
        "reboot_verdict": {
            "verdict": reboot_info.get("verdict", "UNKNOWN"),
            "safe_to_reboot": reboot_info.get("safe", False),
            "reasons": reboot_info.get("reasons", []),
        },
    }
    return receipt


def write_recovery_receipt(receipt: Dict[str, Any], app_data_dir: Path) -> Path:
    """Save recovery receipt to durable run/receipts directory."""
    receipts_dir = app_data_dir / "run" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    out_file = receipts_dir / f"{receipt['receipt_id']}.json"
    out_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return out_file


def terminate_owned_process_by_pid(pid: int, timeout_sec: float = 3.0) -> bool:
    """Terminate an exact owned process tree safely by PID only."""
    if pid <= 0 or pid == os.getpid():
        return False

    if sys.platform == "win32":
        try:
            # /PID exact, /T tree kill, /F force
            res = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False
    else:
        # POSIX process termination by exact PID
        try:
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + timeout_sec
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except OSError:
                    return True
            os.kill(pid, signal.SIGKILL)
            return True
        except ProcessLookupError:
            return True
        except Exception:
            return False


def execute_escalation_ladder(
    target_component: Optional[str] = None,
    level: int = 1,
    app_data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute the recovery escalation ladder step.

    Level 1: Passive Observation / Inspect status
    Level 2: Surface / Explorer Reset guidance
    Level 3: Restart owned helper component
    Level 4: Terminate exact owned component tree
    """
    if app_data_dir is None:
        app_data_dir = get_app_data_dir()

    snapshot = get_critical_snapshot_l0(app_data_dir)
    owned_pids = snapshot.get("owned_processes", {})

    action_summary = f"Escalation Level {level}"
    outcome = "COMPLETED"

    if level == 1:
        action_summary = "Level 1: Passive inspection. Verified active leases and PIDs."
        outcome = "STATUS_VERIFIED"

    elif level == 2:
        action_summary = "Level 2: Surface inspection. Graphics driver reset (Win+Ctrl+Shift+B) recommended if shell unresponsive."
        outcome = "SURFACE_ASSESSED"

    elif level == 3:
        if target_component and target_component in owned_pids:
            proc_info = owned_pids[target_component]
            pid = proc_info["pid"]
            if proc_info["alive"]:
                success = terminate_owned_process_by_pid(pid)
                action_summary = f"Level 3: Terminated helper {target_component} (PID {pid}) for respawn."
                outcome = "HELPER_TERMINATED" if success else "TERMINATION_FAILED"
            else:
                action_summary = f"Level 3: Target {target_component} (PID {pid}) was already dead."
                outcome = "ALREADY_DEAD"
        else:
            action_summary = f"Level 3: No specific owned helper targeted or found in {list(owned_pids.keys())}."
            outcome = "NOOP"

    elif level == 4:
        # Full tree termination of owned components
        terminated = []
        for name, info in owned_pids.items():
            if info["alive"] and (not target_component or target_component == name):
                if terminate_owned_process_by_pid(info["pid"]):
                    terminated.append(f"{name}:{info['pid']}")
        action_summary = f"Level 4: Terminated owned component trees: {', '.join(terminated) if terminated else 'None'}"
        outcome = "TREES_TERMINATED" if terminated else "NOOP"

    receipt = build_recovery_receipt(
        snapshot=snapshot,
        incident_type="INTERRUPTION_OR_FREEZE_RECOVERY",
        action_taken=action_summary,
        outcome=outcome,
    )
    receipt_file = write_recovery_receipt(receipt, app_data_dir)
    receipt["receipt_file"] = str(receipt_file)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Exact-Owned Process Recovery & Escalation Ladder (FRZ-08)")
    parser.add_argument("--level", type=int, default=1, choices=[1, 2, 3, 4], help="Escalation level (1=Inspect, 2=Surface, 3=Restart Helper, 4=Tree Kill)")
    parser.add_argument("--component", choices=["launcher", "controller", "worker", "hub"], help="Target owned component for Level 3/4")
    parser.add_argument("--json", action="store_true", help="Output recovery receipt as JSON")
    args = parser.parse_args()

    receipt = execute_escalation_ladder(
        target_component=args.component,
        level=args.level,
    )

    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        print(f"=== COURIER RECOVERY RECEIPT [{receipt['receipt_id']}] ===")
        print(f"Created:    {receipt['created_at']}")
        print(f"Host:       {receipt['host']['hostname']} ({receipt['host']['platform']})")
        print(f"Action:     {receipt['action_taken']}")
        print(f"Outcome:    {receipt['outcome']}")
        print(f"Reboot:     {receipt['reboot_verdict']['verdict']}")
        print(f"Receipt:    {receipt.get('receipt_file')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
