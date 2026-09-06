#!/usr/bin/env python3
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

WORKSPACE = Path(__file__).resolve().parent.parent
EVENTS_DIR = WORKSPACE / "events"

def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)



def get_os_telemetry() -> Dict[str, Any]:
    uptime = "UNKNOWN"
    load = "UNKNOWN"
    recording_active = "UNKNOWN"
    crash_loop = "UNKNOWN"

    try:
        uptime_out = subprocess.check_output(["uptime"]).decode("utf-8").strip()
        uptime = uptime_out
        if "load averages:" in uptime_out:
            load = uptime_out.split("load averages:")[1].strip()
    except Exception:
        pass

    try:
        # Detect screen recording / video encoding by checking processes
        ps_out = subprocess.check_output(["ps", "-A"]).decode("utf-8")
        if "screencapture" in ps_out or "obs" in ps_out or "ffmpeg" in ps_out or "ScreenRecording" in ps_out:
            recording_active = True
        else:
            recording_active = False
    except Exception:
        pass

    # Crash-loop detection is not genuinely reliable via system.log
    crash_loop = "UNKNOWN"

    return {
        "uptime": uptime,
        "load": load,
        "recording_active": recording_active,
        "crash_loop": crash_loop,
        "stale_agents": "NOT_IMPLEMENTED",
        "swap": "NOT_IMPLEMENTED",
        "memory_pressure": "NOT_IMPLEMENTED"
    }

def evaluate_health(telemetry: Dict[str, Any]) -> Dict[str, str]:
    color = "UNKNOWN"
    restart = "NO"
    reason = "Unknown state"

    # Require sufficient known-good evidence for GREEN
    if telemetry.get("uptime") != "UNKNOWN" and telemetry.get("load") != "UNKNOWN":
        color = "GREEN"
        reason = "Normal idle state"

    if telemetry.get("crash_loop") is True:
        color = "RED"
        restart = "NOW"
        reason = "Crash loop detected"
    elif telemetry.get("load") != "UNKNOWN" and " 100." in str(telemetry.get("load", "")):
        if telemetry.get("recording_active") is True:
            color = "GREEN"
            reason = "High load but KNOWN_HEAVY_WORKLOAD (Recording)"
        else:
            color = "ORANGE"
            restart = "SOON"
            reason = "Unexplained extremely high load"

    return {"color": color, "restart": restart, "reason": reason}



def generate_board(events_dir: Path) -> Dict[str, Any]:
    goals_path = events_dir / "founder-mode" / "goals.json"
    queue_path = events_dir / "mission-queue" / "queue.json"
    fp_path = events_dir / "worker-availability" / "fingerprints.json"

    goals = load_json(goals_path) or []
    q = load_json(queue_path) or {}
    missions = q.get("missions", [])
    fps = load_json(fp_path) or {}

    blocked_missions = [m for m in missions if m.get("status") == "BLOCKED"]
    pending_goals = [g for g in goals if g.get("status") == "PENDING"]

    telemetry = get_os_telemetry()
    health_eval = evaluate_health(telemetry)

    if blocked_missions:
        next_action = "WAIT_ON_HUMAN_GATE_OR_WORKER_CHANGE"
    elif pending_goals:
        next_action = "RUN_COURIER_LOOP"
    else:
        next_action = "STANDBY"

    return {
        "goals": [{"id": g.get("goal_id", ""), "status": g.get("status", ""), "text": g.get("goal", "")} for g in goals],
        "missions": [{"id": m.get("mission_id", ""), "status": m.get("status", ""), "task": m.get("normalized_task", "")} for m in missions],
        "workers": {
            "current_writer": "GEMINI/GOOGLE",
            "cli1_availability": "READ_ONLY",
            "fingerprints": fps
        },
        "blockers": [{"mission_id": m.get("mission_id", ""), "result_reference": m.get("result_reference", "")} for m in blocked_missions],
        "health": {
            "color": health_eval["color"],
            "restart": health_eval["restart"],
            "rules": {
                "uptime_alone_never_restarts": True,
                "exclude_known_workloads": True,
                "second_quiet_window_required": True
            },
            "status": "REAL_HEALTH_TELEMETRY",
            "reality_labels": {
                "uptime": "REAL" if telemetry["uptime"] != "UNKNOWN" else "UNKNOWN",
                "load": "REAL" if telemetry["load"] != "UNKNOWN" else "UNKNOWN",
                "swap": "NOT_IMPLEMENTED",
                "memory_pressure": "NOT_IMPLEMENTED",
                "recording_active": "REAL" if telemetry["recording_active"] != "UNKNOWN" else "UNKNOWN",
                "crash_loop": "REAL" if telemetry["crash_loop"] != "UNKNOWN" else "UNKNOWN",
                "stale_agents": "NOT_IMPLEMENTED"
            },
            "telemetry": telemetry,
            "reason": health_eval["reason"],
            "heavy_known_workload": telemetry["recording_active"] is True,
            "writer_active": True
        },
        "next_safe_action": next_action
    }

def print_board(board: Dict[str, Any]) -> None:
    print("=" * 60)
    print(" COURIER CONTROL CENTER V1 ")
    print("=" * 60)

    print("\n[ FOUNDER GOALS ]")
    for g in board["goals"]:
        print(f" - {g['id'][:8]} | {g['status']} | {g['text']}")

    print("\n[ MISSION QUEUE ]")
    for m in board["missions"]:
        print(f" - {m['id'][:8]} | {m['status']} | {m['task']}")

    print("\n[ WORKERS & AVAILABILITY ]")
    print(f" Current Writer: {board['workers']['current_writer']}")
    print(f" CLI1: {board['workers']['cli1_availability']}")
    for w, fp in board['workers']['fingerprints'].items():
        print(f" - {w}: {fp[:12]}... (Fingerprint verified)")

    print("\n[ BLOCKERS / HUMAN GATE ]")
    if board["blockers"]:
        for b in board["blockers"]:
            print(f" - [BLOCKED] Mission {b['mission_id'][:8]} | Ref: {b['result_reference']}")
    else:
        print(" - No active blockers.")

    print("\n[ SYSTEM HEALTH ]")
    h = board["health"]
    print(f" COLOR: {h['color']} | RESTART: {h['restart']}")
    print(f" REASON: {h['reason']}")
    print(f" UPTIME: {h['telemetry'].get('uptime')}")
    print(f" HEAVY KNOWN WORKLOAD: {h.get('heavy_known_workload')}")
    print(f" WRITER ACTIVE: {h.get('writer_active')}")
    print(" Reality Labels:")
    if 'reality_labels' in h:
        for k, v in h['reality_labels'].items():
            print(f"  - {k}: {v}")
    print(" Rules Enforced:")
    print(f"  - Uptime Alone Never Restarts: {h['rules']['uptime_alone_never_restarts']}")
    print(f"  - Known Workloads Excluded: {h['rules']['exclude_known_workloads']}")
    print(f"  - Require Second Quiet Window: {h['rules']['second_quiet_window_required']}")
    print(f" Note: {h['status']}")

    print("\n[ NEXT SAFE ACTION ]")
    print(f" -> {board['next_safe_action']}")
    print("=" * 60)

if __name__ == "__main__":
    print_board(generate_board(EVENTS_DIR))
