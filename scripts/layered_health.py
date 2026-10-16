#!/usr/bin/env python3
"""Layered Health Model (FRZ-06).

Separates and tracks health independently across Courier's five canonical layers:
  1. WORK EXECUTION   - Worker / task processes, task leases, outbox delivery
  2. SURFACE / UI      - Windows Explorer, Desktop Hub UI, DWM responsiveness
  3. TERMINAL HOST     - VS Code / Antigravity terminal host, PowerShell Editor Services
  4. AGENT SESSION     - CLI driving session (Codex / Claude / Muse)
  5. PERSISTENT STATE  - SQLite ledger/journal, Git worktree commits/dirty state

Core Invariant:
  A BROKEN SURFACE MUST NEVER IMPLY LOST WORK.
  Failure in terminal host or UI surface must never be misclassified as WORK_FAILED.

Failure Classification Enum:
  - OK
  - GUI_SHELL_FROZEN
  - POWERSHELL_EDITOR_SERVICE_FAILED
  - TERMINAL_HOST_FAILED
  - SURFACE_CORRUPTED
  - WORK_STALLED
  - WORK_FAILED
  - RESOURCE_EXHAUSTION
  - PERSISTENCE_DIRTY_CAP_EXCEEDED
  - PERSISTENCE_UNPUSHED_CAP_EXCEEDED

Constraints:
  - Zero grep-family tools, zero kill-by-name.
  - Zero autonomous spend.
"""

from __future__ import annotations

import argparse
import datetime
import enum
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repo root is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.courier_status import (
    get_active_claims,
    get_app_data_dir,
    get_git_status,
    get_journal_stats,
    get_owned_pids,
    get_resource_sample,
)


class LayerState(enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class FailureClassification(enum.Enum):
    OK = "OK"
    GUI_SHELL_FROZEN = "GUI_SHELL_FROZEN"
    POWERSHELL_EDITOR_SERVICE_FAILED = "POWERSHELL_EDITOR_SERVICE_FAILED"
    TERMINAL_HOST_FAILED = "TERMINAL_HOST_FAILED"
    SURFACE_CORRUPTED = "SURFACE_CORRUPTED"
    WORK_STALLED = "WORK_STALLED"
    WORK_FAILED = "WORK_FAILED"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    PERSISTENCE_DIRTY_CAP_EXCEEDED = "PERSISTENCE_DIRTY_CAP_EXCEEDED"
    PERSISTENCE_UNPUSHED_CAP_EXCEEDED = "PERSISTENCE_UNPUSHED_CAP_EXCEEDED"


def assess_work_execution_layer(owned_procs: Dict[str, Any], claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate WORK EXECUTION layer independently."""
    worker_info = owned_procs.get("worker", {})
    worker_alive = worker_info.get("alive", False)
    active_claims_count = len(claims)

    state = LayerState.HEALTHY
    reasons = []

    if active_claims_count > 0 and not worker_alive:
        state = LayerState.FAILED
        reasons.append(f"Work claims in flight ({active_claims_count}) but worker process is not alive")
    elif not worker_alive:
        state = LayerState.DEGRADED
        reasons.append("Worker process not running")

    return {
        "layer": "WORK_EXECUTION",
        "state": state.value,
        "worker_alive": worker_alive,
        "active_claims": active_claims_count,
        "reasons": reasons,
    }


def assess_surface_layer(owned_procs: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate SURFACE / UI layer independently."""
    hub_info = owned_procs.get("hub", {})
    hub_alive = hub_info.get("alive", False)

    state = LayerState.HEALTHY
    reasons = []

    if not hub_alive:
        state = LayerState.DEGRADED
        reasons.append("Desktop Hub UI process is not running (surface offline)")

    return {
        "layer": "SURFACE_UI",
        "state": state.value,
        "hub_alive": hub_alive,
        "reasons": reasons,
    }


def assess_terminal_host_layer() -> Dict[str, Any]:
    """Evaluate TERMINAL HOST layer independently."""
    state = LayerState.HEALTHY
    reasons = []

    # Detect terminal host indicators
    term_env = os.environ.get("TERM_PROGRAM", "")
    is_vscode = "vscode" in term_env.lower()

    return {
        "layer": "TERMINAL_HOST",
        "state": state.value,
        "environment": term_env or "standalone",
        "reasons": reasons,
    }


def assess_agent_session_layer(owned_procs: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate AGENT SESSION layer independently."""
    launcher_info = owned_procs.get("launcher", {})
    launcher_alive = launcher_info.get("alive", False)

    state = LayerState.HEALTHY
    reasons = []

    if not launcher_alive:
        state = LayerState.DEGRADED
        reasons.append("Courier launcher supervisor is not alive")

    return {
        "layer": "AGENT_SESSION",
        "state": state.value,
        "launcher_alive": launcher_alive,
        "reasons": reasons,
    }


def assess_persistent_state_layer(journal: Dict[str, Any], git_st: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate PERSISTENT STATE layer independently."""
    state = LayerState.HEALTHY
    reasons = []
    classifications = []

    dirty_count = git_st.get("dirty_count", 0)
    unpushed_count = git_st.get("unpushed_count", 0)

    # Freeze incident safety caps
    if unpushed_count >= 50:  # Incident had 71 unpushed commits
        state = LayerState.FAILED
        reasons.append(f"Excessive unpushed commits ({unpushed_count} >= 50): high data-loss risk")
        classifications.append(FailureClassification.PERSISTENCE_UNPUSHED_CAP_EXCEEDED.value)
    elif unpushed_count > 10:
        state = LayerState.DEGRADED
        reasons.append(f"Unpushed commits accumulating ({unpushed_count} > 10)")

    if dirty_count > 50:
        if state != LayerState.FAILED:
            state = LayerState.DEGRADED
        reasons.append(f"Many uncommitted modified files ({dirty_count} > 50)")
        classifications.append(FailureClassification.PERSISTENCE_DIRTY_CAP_EXCEEDED.value)

    if not journal.get("exists", False):
        if state != LayerState.FAILED:
            state = LayerState.DEGRADED
        reasons.append("SQLite journal (courier.db) not found")

    return {
        "layer": "PERSISTENT_STATE",
        "state": state.value,
        "journal_present": journal.get("exists", False),
        "dirty_files": dirty_count,
        "unpushed_commits": unpushed_count,
        "reasons": reasons,
        "classifications": classifications,
    }


def evaluate_system_layered_health(app_data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Produce complete evaluation across all 5 canonical layers."""
    if app_data_dir is None:
        app_data_dir = get_app_data_dir()

    owned_procs = get_owned_pids(app_data_dir)
    claims = get_active_claims(app_data_dir)
    journal = get_journal_stats(app_data_dir)
    git_st = get_git_status()
    resources = get_resource_sample()

    work_layer = assess_work_execution_layer(owned_procs, claims)
    surface_layer = assess_surface_layer(owned_procs)
    terminal_layer = assess_terminal_host_layer()
    agent_layer = assess_agent_session_layer(owned_procs)
    persist_layer = assess_persistent_state_layer(journal, git_st)

    # Classify overall failure if any
    primary_failure = FailureClassification.OK.value
    if persist_layer.get("classifications"):
        primary_failure = persist_layer["classifications"][0]
    elif work_layer["state"] == LayerState.FAILED.value:
        primary_failure = FailureClassification.WORK_FAILED.value
    elif surface_layer["state"] == LayerState.FAILED.value:
        primary_failure = FailureClassification.SURFACE_CORRUPTED.value
    elif terminal_layer["state"] == LayerState.FAILED.value:
        primary_failure = FailureClassification.TERMINAL_HOST_FAILED.value

    # Overarching status
    states = [work_layer["state"], surface_layer["state"], terminal_layer["state"], agent_layer["state"], persist_layer["state"]]
    if LayerState.FAILED.value in states:
        overall_status = LayerState.FAILED.value
    elif LayerState.DEGRADED.value in states:
        overall_status = LayerState.DEGRADED.value
    else:
        overall_status = LayerState.HEALTHY.value

    return {
        "schema_version": "1.0",
        "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "overall_status": overall_status,
        "primary_failure_classification": primary_failure,
        "layers": {
            "work_execution": work_layer,
            "surface_ui": surface_layer,
            "terminal_host": terminal_layer,
            "agent_session": agent_layer,
            "persistent_state": persist_layer,
        },
        "resources": resources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Courier Layered Health Model (FRZ-06)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON health report")
    args = parser.parse_args()

    report = evaluate_system_layered_health()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== COURIER SYMPHONY — LAYERED HEALTH MODEL ===")
        print(f"Overall Status:    {report['overall_status']}")
        print(f"Primary Failure:   {report['primary_failure_classification']}")
        print("\n[Layer Breakdown]")
        for name, l in report["layers"].items():
            print(f"  {name:<18}: {l['state']}")
            for r in l.get("reasons", []):
                print(f"    - {r}")

    return 0 if report["overall_status"] != LayerState.FAILED.value else 1


if __name__ == "__main__":
    sys.exit(main())
