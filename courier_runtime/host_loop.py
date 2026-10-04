"""Host loop: the smallest real wiring from provider signals to Kirby.

A provider going idle after one task must not wait for Dennis. This loop
tails one append-only provider signal file (line protocol documented in
courier_runtime.provider_events), feeds only NEW lines to Kirby, runs the
fast health tick at most every HEALTH_TICK_S, and records at most ONE wake
notice per pending continuation.

It never prequeues prompts, never opens windows or processes, and never
kills anything: session start/termination stay Kirby's injected callables.
Delivery of a pending wake to the provider (``Kirby.deliver``) stays the
provider lane's job; this loop only makes the wake exist and visible.
"""
import argparse
import json
import os
import time

from courier_runtime.continuity import HEALTH_TICK_S
from courier_runtime.provider_events import drive, read_new_lines

NOTICES = "wakeups.jsonl"


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def run_once(kirby, slot, signal_path, state):
    """One loop iteration. ``state`` = {"offset": int, "last_tick": float,
    "notified": {slot: [session_id, workkey, token]}}; mutated in place.

    Returns (results, actions, notices). Missing/truncated signal file is
    fail-closed: no lines fed, offset reset, tick still runs on cadence.
    """
    results, actions, notices = [], {}, []
    size = _file_size(signal_path)
    if size is None:
        pass                                                    # no signal file yet: tick only
    else:
        if state.get("offset", 0) > size:
            state["offset"] = 0                                 # file rotated/truncated: reread
        lines, state["offset"] = read_new_lines(signal_path, state["offset"])
        if lines:
            results = drive(kirby, slot, lines)                 # only new lines; never prequeued
    if kirby.clock() - state.get("last_tick", 0.0) >= HEALTH_TICK_S:
        actions = kirby.tick()                                  # fast fallback + 15-min snapshot cadence
        state["last_tick"] = kirby.clock()
    notices = _notice(kirby, slot, state)
    return results, actions, notices


def _notice(kirby, slot, state):
    """Append one wake notice when THIS slot newly holds a pending wake.

    Duplicate IDLE lines while a wake is pending (or while the provider is
    working) produce no further notice: the recorded triple
    (session_id, workkey, token) only changes when a genuinely new
    continuation arises.
    """
    from courier_runtime.continuity import WAKE_PENDING

    session = kirby.sessions.get(slot)
    if session is None or session.state != WAKE_PENDING:
        return []
    triple = [session.session_id, session.workkey, session.token]
    if state.get("notified", {}).get(slot) == triple:
        return []
    state.setdefault("notified", {})[slot] = triple
    record = {"at": kirby.clock(), "slot": slot, "session_id": session.session_id,
              "workkey": session.workkey, "token": session.token}
    with open(kirby.path.parent / NOTICES, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return [record]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tail provider signals into Kirby.")
    ap.add_argument("--state", required=True, help="Kirby state file (kirby.json)")
    ap.add_argument("--slot", required=True)
    ap.add_argument("--signals", required=True, help="Provider signal file to tail")
    ap.add_argument("--host", default="host")
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args(argv)

    from courier_runtime.continuity import Kirby
    kirby = Kirby(args.state, args.host)
    state = {"offset": 0, "last_tick": 0.0, "notified": {}}
    while True:
        run_once(kirby, args.slot, args.signals, state)
        if args.once:
            return 0
        time.sleep(args.interval)
