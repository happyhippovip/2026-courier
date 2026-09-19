#!/usr/bin/env python3
"""Deterministic Eight Bodyguards Reserve Worker Pool for 2026 Courier.

The 8 Bodyguards (Alpha through Hotel) are universal RESERVE WORKER SLOTS.
They are NOT continuously running model workers (STANDBY = 0 model calls, 0.00 EUR).

When Chief needs additional capacity or SNITCH flags a stalled specialist:
1. Chief checks if primary specialist is free
2. Chief checks if deterministic/local solution is available
3. Chief checks if a suitable Bodyguard is available in STANDBY
4. Chief verifies capability requirements
5. If capabilities satisfied, assigns Bodyguard with temporary role;
   otherwise marks CAPABILITY_MISMATCH (no fake capability claims!).

On task completion: Bodyguard -> RETURNING -> STANDBY.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
EVENTS_DIR = COURIER_DIR / "events"
STATES_DIR = EVENTS_DIR / "agent-states"

BODYGUARD_REGISTRY = [
    {"slot": "BG-01", "callsign": "ALPHA", "id": "agent-bodyguard-alpha", "name": "BODYGUARD ALPHA"},
    {"slot": "BG-02", "callsign": "BRAVO", "id": "agent-bodyguard-bravo", "name": "BODYGUARD BRAVO"},
    {"slot": "BG-03", "callsign": "CHARLIE", "id": "agent-bodyguard-charlie", "name": "BODYGUARD CHARLIE"},
    {"slot": "BG-04", "callsign": "DELTA", "id": "agent-bodyguard-delta", "name": "BODYGUARD DELTA"},
    {"slot": "BG-05", "callsign": "ECHO", "id": "agent-bodyguard-echo", "name": "BODYGUARD ECHO"},
    {"slot": "BG-06", "callsign": "FOXTROT", "id": "agent-bodyguard-foxtrot", "name": "BODYGUARD FOXTROT"},
    {"slot": "BG-07", "callsign": "GOLF", "id": "agent-bodyguard-golf", "name": "BODYGUARD GOLF"},
    {"slot": "BG-08", "callsign": "HOTEL", "id": "agent-bodyguard-hotel", "name": "BODYGUARD HOTEL"},
]

ALLOWED_TEMP_ROLES = {
    "VISUAL_IMPLEMENTATION",
    "TECHNICAL_WORKER",
    "DIAGNOSTIC_WORKER",
    "CONTENT_WORKER",
    "RESEARCH_WORKER",
    "QA_WORKER",
    "PERMISSION_DIAGNOSTIC_WORKER",
}

SUPPORTED_CAPABILITIES = {
    "local_filesystem",
    "deterministic_execution",
    "courier_envelope_handling",
    "git_inspection",
    "media_metadata",
    "godot_render_verification",
    "state_aggregation",
    "test_runner",
    "diff_analysis",
    "permission_audit",
    "sandbox_rule_matching",
}



def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def generate_bodyguard_speech(state: str, callsign: str, role: str | None = None) -> str:
    """Deterministic speech bubbles corresponding to bodyguard lifecycle states."""
    if state == "STANDBY":
        return "Ready for reserve duty."
    if state == "ASSIGNED":
        return f"Temporary role {role or 'ACCEPTED'} received. Preparing task."
    if state == "PREPARING":
        return "Loading task context and validating contracts."
    if state == "WORKING":
        return "I'm covering this task while the specialist is busy."
    if state == "RETURNING":
        return "Result delivered to Courier. Returning to standby."
    if state == "CAPABILITY_MISMATCH":
        return "Required capability is unavailable. Flagging capability mismatch."
    if state == "BLOCKED":
        return "Task blocked. Standing by for Chief instruction."
    return f"Bodyguard {callsign} on reserve."


class BodyguardPoolManager:
    """Manages the 8 Bodyguard reserve slots, temporary roles, and state files."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.states_dir = repo_dir / "events/agent-states"
        self.states_dir.mkdir(parents=True, exist_ok=True)

    def initialize_pool(self, force_reset: bool = False) -> list[dict[str, Any]]:
        """Ensure all 8 Bodyguards exist in agent-states directory in STANDBY state."""
        states = []
        for bg in BODYGUARD_REGISTRY:
            path = self.states_dir / f"{bg['id']}.json"
            if force_reset or not path.exists():
                state = {
                    "schema_version": "2.0",
                    "id": bg["id"],
                    "slot": bg["slot"],
                    "callsign": bg["callsign"],
                    "name": bg["name"],
                    "role": "RESERVE WORKER SLOT",
                    "temporary_role": None,
                    "state": "STANDBY",
                    "task": "Reserve Duty (Standby)",
                    "progress": 0.0,
                    "workflow": None,
                    "correlation_id": None,
                    "last_action": "Standing by in Bodyguard Ready Room",
                    "next_action": "Awaiting Chief assignment",
                    "speech": generate_bodyguard_speech("STANDBY", bg["callsign"]),
                    "result": None,
                    "blocked": False,
                    "human_gate": None,
                    "supported_capabilities": sorted(SUPPORTED_CAPABILITIES),
                    "model_calls_incurred": 0,
                    "updated_at": iso_now(),
                }
                save_json(path, state)
                states.append(state)
            else:
                states.append(load_json(path))
        return states

    def get_all_bodyguards(self) -> list[dict[str, Any]]:
        """Return current states of all 8 Bodyguards."""
        states = []
        for bg in BODYGUARD_REGISTRY:
            path = self.states_dir / f"{bg['id']}.json"
            if path.exists():
                states.append(load_json(path))
            else:
                self.initialize_pool()
                return self.get_all_bodyguards()
        return states

    def get_available_bodyguards(self) -> list[dict[str, Any]]:
        """Return all bodyguards currently in STANDBY state."""
        return [bg for bg in self.get_all_bodyguards() if bg.get("state") == "STANDBY"]

    def assign_bodyguard(
        self,
        callsign: str | None,
        task_id: str,
        workflow_id: str,
        correlation_id: str,
        temporary_role: str = "TECHNICAL_WORKER",
        required_capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Assign a bodyguard to a task with a temporary role after capability verification."""
        all_bgs = self.get_all_bodyguards()
        bg_to_assign = None

        if callsign:
            for bg in all_bgs:
                if bg.get("callsign") == callsign.upper():
                    if bg.get("state") != "STANDBY":
                        raise ValueError(f"Bodyguard {callsign} is busy (state: {bg.get('state')})")
                    bg_to_assign = bg
                    break
            if not bg_to_assign:
                raise ValueError(f"Bodyguard {callsign} not found")
        else:
            available = [b for b in all_bgs if b.get("state") == "STANDBY"]
            if available:
                bg_to_assign = available[0]

        if not bg_to_assign:
            raise ValueError("No available Bodyguard in STANDBY state")


        target_callsign = bg_to_assign["callsign"]
        path = self.states_dir / f"{bg_to_assign['id']}.json"

        # Check required capabilities
        reqs = required_capabilities or []
        unsupported = [c for c in reqs if c not in SUPPORTED_CAPABILITIES]
        if unsupported:
            # CAPABILITY_MISMATCH: Do not claim capabilities that do not exist!
            state = {
                **bg_to_assign,
                "state": "CAPABILITY_MISMATCH",
                "temporary_role": temporary_role,
                "task": task_id,
                "workflow": workflow_id,
                "correlation_id": correlation_id,
                "last_action": f"Capability mismatch: unsupported capabilities {unsupported}",
                "next_action": "Chief must route to human or specialized external capability",
                "speech": generate_bodyguard_speech("CAPABILITY_MISMATCH", target_callsign),
                "blocked": True,
                "updated_at": iso_now(),
            }
            save_json(path, state)
            return state

        # Valid Assignment
        state = {
            **bg_to_assign,
            "state": "ASSIGNED",
            "temporary_role": temporary_role,
            "task": task_id,
            "workflow": workflow_id,
            "correlation_id": correlation_id,
            "progress": 0.1,
            "last_action": f"Assigned temporary role {temporary_role} for task {task_id}",
            "next_action": "Executing task steps in local sandbox",
            "speech": generate_bodyguard_speech("ASSIGNED", target_callsign, temporary_role),
            "blocked": False,
            "updated_at": iso_now(),
        }
        save_json(path, state)
        return state

    def update_progress(
        self,
        callsign: str,
        progress: float,
        action: str,
        working: bool = True,
    ) -> dict[str, Any]:
        """Update bodyguard execution progress."""
        for bg in BODYGUARD_REGISTRY:
            if bg["callsign"] == callsign.upper():
                path = self.states_dir / f"{bg['id']}.json"
                current = load_json(path)
                state_val = "WORKING" if working else current.get("state", "WORKING")
                updated = {
                    **current,
                    "state": state_val,
                    "progress": progress,
                    "last_action": action,
                    "speech": generate_bodyguard_speech(state_val, bg["callsign"], current.get("temporary_role")),
                    "updated_at": iso_now(),
                }
                save_json(path, updated)
                return updated
        raise ValueError(f"Unknown bodyguard callsign: {callsign}")

    def complete_task(
        self,
        callsign: str,
        result_file: str | None = None,
    ) -> dict[str, Any]:
        """Mark task as returning/completed and transition bodyguard back to STANDBY."""
        for bg in BODYGUARD_REGISTRY:
            if bg["callsign"] == callsign.upper():
                path = self.states_dir / f"{bg['id']}.json"
                current = load_json(path)
                # First step: RETURNING
                returning_state = {
                    **current,
                    "state": "RETURNING",
                    "progress": 1.0,
                    "last_action": f"Result delivered to Courier: {result_file or 'COMPLETED'}",
                    "next_action": "Returning to Standby in Ready Room",
                    "speech": generate_bodyguard_speech("RETURNING", bg["callsign"]),
                    "result": {"result_file": result_file} if result_file else None,
                    "updated_at": iso_now(),
                }
                save_json(path, returning_state)

                # Reset to STANDBY
                standby_state = {
                    **returning_state,
                    "state": "STANDBY",
                    "temporary_role": None,
                    "task": "Reserve Duty (Standby)",
                    "progress": 0.0,
                    "workflow": None,
                    "correlation_id": None,
                    "last_action": f"Completed prior task {current.get('task')}. Back on reserve.",
                    "next_action": "Awaiting Chief assignment",
                    "speech": generate_bodyguard_speech("STANDBY", bg["callsign"]),
                    "result": None,
                    "updated_at": iso_now(),
                }
                save_json(path, standby_state)
                return standby_state
        raise ValueError(f"Unknown bodyguard callsign: {callsign}")

    def release_bodyguard(self, callsign: str) -> dict[str, Any]:
        """Explicitly reset a bodyguard back to STANDBY state."""
        return self.complete_task(callsign)



def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Eight Bodyguards reserve pool.")
    parser.add_argument("--init", action="store_true", help="Initialize all 8 Bodyguards in STANDBY")
    parser.add_argument("--status", action="store_true", help="Print status of all 8 Bodyguards")
    parser.add_argument("--assign", type=str, help="Callsign to assign (e.g. ALPHA)")
    parser.add_argument("--role", type=str, default="TECHNICAL_WORKER", help="Temporary role")
    parser.add_argument("--task", type=str, default="TASK-RESERVE-001", help="Task ID")
    parser.add_argument("--workflow", type=str, default="WF-CHIEF-RESERVE", help="Workflow ID")
    parser.add_argument("--correlation", type=str, default="corr-reserve-001", help="Correlation ID")
    parser.add_argument("--complete", type=str, help="Callsign to complete (e.g. ALPHA)")
    args = parser.parse_args()

    manager = BodyguardPoolManager()
    if args.init:
        manager.initialize_pool(force_reset=True)
        print("Initialized 8 Bodyguards in STANDBY.")
        return 0

    if args.assign:
        res = manager.assign_bodyguard(
            callsign=args.assign,
            task_id=args.task,
            workflow_id=args.workflow,
            correlation_id=args.correlation,
            temporary_role=args.role,
        )
        print(json.dumps(res, indent=2))
        return 0

    if args.complete:
        res = manager.complete_task(callsign=args.complete, result_file="result.json")
        print(json.dumps(res, indent=2))
        return 0

    status = manager.get_all_bodyguards()
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
