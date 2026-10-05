"""Courier visual language: the red beam and the green proof.

Born from the first product video (2026-10-04): a window storm, the bird
removes the noise, and only the real work stays, linked by green lines.
The overlay, video and any status UI use exactly this mapping:

  RED    beam     a surface/task that was actually closed or reclaimed
  GREEN  proof    work that is verified done, or a live surface safely reused
  AMBER  waiting  waiting on a human, the OS, a wake or capacity (never "done")
  BLUE   working  in progress; no claim about the outcome yet
  GREY   unknown  orphaned / not ours / not classified: shown, never touched

Laws carried into the picture:
  * No shadow, no claim: GREEN only for states the runtime can prove.
  * The red beam only hits what reclaim()/reconcile() really closed;
    anything unsafe stays PARKED (amber), it is never "beamed away".
  * Every runtime state has exactly one colour (enforced by tests), so a new
    state cannot ship without a decision about how it is shown.
"""

from courier_runtime import continuity as _c
from courier_runtime import surfaces as _s

RED, GREEN, AMBER, BLUE, GREY = "RED", "GREEN", "AMBER", "BLUE", "GREY"

# Hex values follow the video: emerald bird light and a warm red beam.
HEX = {RED: "#FF3B30", GREEN: "#22E39A", AMBER: "#FFB020", BLUE: "#4C8DFF", GREY: "#8A8F98"}

SURFACE_STATE = {
    _s.STARTING: BLUE,
    _s.WORKING: BLUE,
    _s.WAITING_FOR_USER: AMBER,
    _s.WAITING_FOR_OS: AMBER,
    _s.IDLE_READY: GREEN,
    _s.PARKED: AMBER,
    _s.COMPLETED: GREEN,
    _s.TERMINAL_HOST_FAILED: RED,
    _s.SURFACE_CORRUPTED: RED,
}

ADMISSION = {           # SurfaceSupervisor.admit() decisions
    "REUSE": GREEN,
    "COALESCED": GREEN,
    "HEADLESS": BLUE,
    "OPEN": BLUE,
    "QUEUED": AMBER,
}

RECONCILE = {           # SurfaceSupervisor.reconcile() classifications
    "COMPLETED": GREEN,
    "REUSABLE": GREEN,
    "STILL_ALIVE": BLUE,
    "STALE": RED,
    "ORPHANED": GREY,
}

WORKKEY_STATE = {
    _c.OPEN: BLUE,
    _c.CLAIMED: BLUE,
    _c.DONE: GREEN,
    _c.BLOCKED: AMBER,
    _c.FAILED_FINAL: RED,
}

SESSION_STATE = {
    _c.WORKING: BLUE,
    _c.IDLE: GREEN,
    _c.WAKE_PENDING: AMBER,
    _c.WAITING_FOR_USER: AMBER,
    _c.RECOVERING: AMBER,
    _c.RETIRED: GREY,
}

TABLES = {"surface": SURFACE_STATE, "admission": ADMISSION, "reconcile": RECONCILE,
          "workkey": WORKKEY_STATE, "session": SESSION_STATE}


def colour(kind, state):
    """Colour for a state. Unknown states are GREY, never GREEN."""
    return TABLES[kind].get(state, GREY)


def beam_plan(reclaim_results=(), reconcile_result=None):
    """Turn real runtime results into the animation the video shows.

    reclaim_results: list returned by SurfaceSupervisor.reclaim_idle()/reclaim().
    reconcile_result: dict returned by SurfaceSupervisor.reconcile().
    Returns [(surface_id, effect)] where effect is "red_beam", "green_link",
    "amber_hold" or "grey_mark". Only surfaces with closed=True get a red beam.
    """
    plan = []
    for r in reclaim_results:
        plan.append((r["surface_id"], "red_beam" if r.get("closed") else "amber_hold"))
    effect = {RED: "red_beam", GREEN: "green_link", AMBER: "amber_hold", BLUE: "green_link", GREY: "grey_mark"}
    for sid, cls in sorted((reconcile_result or {}).items()):
        c = colour("reconcile", cls)
        # STILL_ALIVE is working, not proven: link it, but it is not counted as verified.
        plan.append((sid, effect[c]))
    return plan
