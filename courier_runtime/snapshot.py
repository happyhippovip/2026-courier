"""Critical Snapshot Level 0: structured state of Courier's own work, no pixels.

collect() looks only at processes Courier recorded as its own (ownership
Registry) plus progress signals the runtime already has. classify() turns a
session's snapshot into a liveness verdict from runtime evidence; a visual
hint can be attached but can never decide a state on its own.
"""
import time
import uuid

import psutil

from courier_runtime.ownership import is_same_process

WORKING, QUIET, IDLE_READY, NEEDS_USER = "WORKING", "QUIET", "IDLE_READY", "WAITING_FOR_USER_PERMISSION"
OS_WAIT, SURFACE_CORRUPTED, TERMINAL_HOST_FAILED = "WAITING_FOR_OS_PERMISSION", "SURFACE_CORRUPTED", "TERMINAL_HOST_FAILED"
FAILED, PROBING = "FAILED", "PROBING"


def collect(registry, sessions, host_id, trigger, clock=time.time):
    """sessions: {session_id: {"workkey", "last_progress_at", "turn_complete", "owes_work",
    "pending_permission": None|"user"|"os", "os_blocked_operation": bool, "surface_ok": bool,
    "exit_code": None|int}} - runtime facts, never screen contents."""
    by_workkey = {}
    for record in registry.owned():
        by_workkey.setdefault(record.workkey, []).append(record)
    out = []
    for session_id, s in sessions.items():
        records = by_workkey.get(s["workkey"], [])
        # A later dead record must not hide an earlier live one.
        live = next((r for r in records if is_same_process(r)), None)
        record = live if live is not None else (records[-1] if records else None)
        alive = live is not None
        out.append({
            "session_id": session_id, "workkey": s["workkey"],
            "process": None if record is None else {"pid": record.pid, "create_time": record.create_time,
                                                    "alive": alive, "exit_code": s.get("exit_code")},
            "progress": {"last_progress_at": s.get("last_progress_at")},
            "turn": {"complete": bool(s.get("turn_complete")), "owes_work": bool(s.get("owes_work"))},
            "permission": {"pending": s.get("pending_permission"),
                           "os_blocked_operation": bool(s.get("os_blocked_operation"))},
            "surface_ok": s.get("surface_ok", True),
        })
    return {"snapshot_id": "cs0-" + uuid.uuid4().hex, "schema": 1, "level": 0, "host_id": host_id,
            "taken_at": clock(), "trigger": trigger, "sessions": out,
            "device": {"cpu_pct": psutil.cpu_percent(interval=None),
                       "mem_pct": psutil.virtual_memory().percent}}


def classify(session, now, quiet_after_s=120, visual_hint=None):
    """Return {"state", "evidence", "action"} for one session of a Level-0 snapshot.

    visual_hint (e.g. "permission_dialog_visible") is recorded but never decisive.
    """
    proc = session["process"]
    evidence = []
    if proc is None:
        return {"state": PROBING, "evidence": ["no owned process recorded"], "action": "PROBE",
                "visual_hint": visual_hint}
    if not proc["alive"]:
        code = proc.get("exit_code")
        if code not in (None, 0):
            return {"state": TERMINAL_HOST_FAILED if session.get("is_terminal_host") else FAILED,
                    "evidence": [f"exit_code={code}"], "action": "RECOVER", "visual_hint": visual_hint}
        if session["turn"]["complete"] and not session["turn"]["owes_work"]:
            return {"state": IDLE_READY, "evidence": ["process ended after a complete turn"], "action": "NONE",
                    "visual_hint": visual_hint}
        return {"state": PROBING, "evidence": ["owned process gone without exit evidence"], "action": "PROBE",
                "visual_hint": visual_hint}
    evidence.append(f"pid {proc['pid']} alive with recorded start time")
    pending = session["permission"]["pending"]
    if pending == "user":
        return {"state": NEEDS_USER, "evidence": evidence + ["permission request pending"], "action": "NEEDS_YOU",
                "visual_hint": visual_hint}
    if pending == "os" and session["permission"]["os_blocked_operation"]:
        return {"state": OS_WAIT, "evidence": evidence + ["OS request blocks an operation"], "action": "NEEDS_YOU",
                "visual_hint": visual_hint}
    last = session["progress"]["last_progress_at"]
    progressing = last is not None and now - last <= quiet_after_s
    if not session["surface_ok"] and progressing:
        return {"state": SURFACE_CORRUPTED, "evidence": evidence + ["work progressing, surface broken"],
                "action": "RECONNECT_SURFACE", "visual_hint": visual_hint}
    if session["turn"]["complete"] and not session["turn"]["owes_work"]:
        return {"state": IDLE_READY, "evidence": evidence + ["turn complete, nothing owed"], "action": "NONE",
                "visual_hint": visual_hint}
    if progressing:
        return {"state": WORKING, "evidence": evidence + ["recent progress"], "action": "NONE",
                "visual_hint": visual_hint}
    return {"state": QUIET, "evidence": evidence + ["no progress within budget"], "action": "PROBE",
            "visual_hint": visual_hint}
