"""Host loop: the smallest real wiring from provider signals to Kirby.

A provider going idle after one task must not wait for Dennis. This loop
tails one append-only provider signal file (line protocol documented in
courier_runtime.provider_events), feeds only NEW lines to Kirby, runs the
fast health tick at most every HEALTH_TICK_S, and records at most ONE wake
notice per pending continuation.

It never prequeues prompts, never opens windows or processes, and never
kills anything: session start/termination stay Kirby's injected callables.
When the queue is idle, ``main`` blocks on ``wait_for_wakeup`` instead of
sleeping in a loop. A health tick still runs only from ``run_once``.
``drain_pending`` is the provider lane's take-one-wake contract;
``emit_signal`` is how lanes append protocol lines to the signal file.
"""
import argparse
import json
import os
import sys
import tempfile
import time

from courier_runtime.continuity import HEALTH_TICK_S, IDLE, WAKE_PENDING
from courier_runtime.provider_events import drive, read_new_lines

NOTICES = "wakeups.jsonl"
LOOP_STATE_FILE = "host_loop_state.json"


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def load_loop_state(kirby):
    """Load persisted host-loop offset and notice state across process restarts."""
    p = kirby.path.parent / LOOP_STATE_FILE
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return {
                "offset": int(d.get("offset", 0)),
                "last_tick": float(d.get("last_tick", 0.0)),
                "notified": dict(d.get("notified", {})),
            }
        except (OSError, ValueError, TypeError):
            pass
    return {"offset": 0, "last_tick": 0.0, "notified": {}}


def _save_loop_state(kirby, state):
    """Persist host-loop offset and notice state atomically."""
    kirby.path.parent.mkdir(parents=True, exist_ok=True)
    p = kirby.path.parent / LOOP_STATE_FILE
    payload = {
        "offset": int(state.get("offset", 0)),
        "last_tick": float(state.get("last_tick", 0.0)),
        "notified": dict(state.get("notified", {})),
    }
    fd, tmp = tempfile.mkstemp(dir=kirby.path.parent, prefix=".loop_state.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True)
    os.replace(tmp, p)


def emit_signal(signal_path, line):
    """Provider lanes append one protocol line (see provider_events). Atomic
    append + fsync; unknown lines stay fail-closed downstream (IGNORED)."""
    from pathlib import Path

    p = Path(signal_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write((line or "") + "\n")
        f.flush()
        os.fsync(f.fileno())
    return line


def drain_pending(kirby, slot):
    """Provider lane takes the single pending wake, if any. Returns the
    workkey and moves the session to WORKING, else None. A second call
    returns None: one wake becomes exactly one execution."""
    session = kirby.sessions.get(slot)
    if session is None or session.state != WAKE_PENDING:
        return None
    return kirby.deliver(slot)


def run_once(kirby, slot, signal_path, state, dispatch=None):
    """One loop iteration. ``state`` = {"offset": int, "last_tick": float,
    "notified": {slot: [session_id, workkey, token]}}; mutated in place.

    If ``dispatch`` (or ``kirby.dispatcher``) is provided, a pending wake on
    ``slot`` is automatically drained via ``drain_pending`` and handed to
    ``dispatch(slot, workkey, session)`` exactly once.
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
    session = kirby.sessions.get(slot)
    if (
        session is not None
        and session.state == IDLE
        and kirby.has_ready_work()
        and kirby.counters.get("completions", 0) > 0
    ):
        results.append(kirby.wake(slot))
    if kirby.clock() - state.get("last_tick", 0.0) >= HEALTH_TICK_S:
        actions = kirby.tick()                                  # fast fallback + 15-min snapshot cadence
        state["last_tick"] = kirby.clock()
    notices = _notice(kirby, slot, state)
    dispatch_fn = dispatch if dispatch is not None else getattr(kirby, "dispatcher", None)
    if dispatch_fn is not None:
        workkey = drain_pending(kirby, slot)
        if workkey is not None:
            s = kirby.sessions[slot]
            kirby._log("dispatches.jsonl", {
                "at": kirby.clock(),
                "slot": slot,
                "session_id": s.session_id,
                "workkey": workkey,
                "token": s.token,
            })
            dispatch_fn(slot, workkey, s)
    _save_loop_state(kirby, state)
    return results, actions, notices


def run_until_idle(kirby, slot, signal_path, state, dispatch=None, max_steps=500):
    """Drive bounded autonomous continuation until READY is empty or blocked/in-flight."""
    steps = 0
    while steps < max_steps:
        steps += 1
        results, actions, notices = run_once(kirby, slot, signal_path, state, dispatch=dispatch)
        if _queue_idle(kirby):
            break
        size = _file_size(signal_path)
        has_unread = size is not None and size > state.get("offset", 0)
        session = kirby.sessions.get(slot)
        has_pending = session is not None and session.state == WAKE_PENDING
        if not has_unread and not has_pending and not results and not actions and not notices:
            break
    return steps


def _notice(kirby, slot, state):
    """Append one wake notice when THIS slot newly holds a pending wake.

    Duplicate IDLE lines while a wake is pending (or while the provider is
    working) produce no further notice: the recorded triple
    (session_id, workkey, token) only changes when a genuinely new
    continuation arises.
    """
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


def _queue_idle(kirby):
    """No open or claimed work and no session waiting to be woken."""
    if any(item.state in ("OPEN", "CLAIMED") for item in kirby.workkeys.values()):
        return False
    return not any(session.state not in ("IDLE", "RETIRED") for session in kirby.sessions.values())


def wakeup_backend(platform=None):
    """Linux blocks on inotify. Windows blocks on ReadDirectoryChangesW."""
    name = sys.platform if platform is None else platform
    if name == "win32":
        return "read_directory_changes"
    return "inotify"


def wait_for_wakeup(path):
    """Block until the signal directory changes. One wait, no sleep loop."""
    if wakeup_backend() == "read_directory_changes":
        return _wait_windows(path)
    return _wait_inotify(path)


def _wait_windows(path, kernel32=None):
    """One blocking ReadDirectoryChangesW. ``kernel32`` is injectable in tests."""
    import ctypes

    kernel = kernel32 if kernel32 is not None else ctypes.windll.kernel32
    directory = os.path.dirname(os.path.abspath(path)) or "."
    handle = kernel.CreateFileW(directory, 0x0001, 0x0001 | 0x0002 | 0x0004, None, 3, 0x02000000, None)
    if handle in (-1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
        raise OSError("CreateFileW")
    try:
        buf = ctypes.create_string_buffer(4096)
        returned = ctypes.c_uint32()
        ok = kernel.ReadDirectoryChangesW(
            handle, buf, 4096, True, 0x17, ctypes.byref(returned), None, None,
        )
        if not ok:
            raise OSError("ReadDirectoryChangesW")
    finally:
        kernel.CloseHandle(handle)


def _wait_inotify(path):
    """Block until the signal directory changes. One select, no sleep loop."""
    import ctypes
    import ctypes.util
    import select

    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    libc.inotify_init1.argtypes = [ctypes.c_int]
    libc.inotify_init1.restype = ctypes.c_int
    libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    libc.inotify_add_watch.restype = ctypes.c_int
    libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
    libc.inotify_rm_watch.restype = ctypes.c_int
    handle = libc.inotify_init1(0)
    if handle < 0:
        raise OSError(ctypes.get_errno(), "inotify_init1")
    parent = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(parent, exist_ok=True)
    mask = 0x00000002 | 0x00000008 | 0x00000080 | 0x00000100
    watch = libc.inotify_add_watch(handle, os.fsencode(parent), mask)
    if watch < 0:
        err = ctypes.get_errno()
        os.close(handle)
        raise OSError(err, "inotify_add_watch")
    try:
        select.select([handle], [], [])
        os.read(handle, 4096)
    finally:
        libc.inotify_rm_watch(handle, watch)
        os.close(handle)


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
    kirby.reconcile_after_restart()
    state = load_loop_state(kirby)
    while True:
        run_once(kirby, args.slot, args.signals, state)
        if args.once:
            return 0
        if _queue_idle(kirby):
            wait_for_wakeup(args.signals)
        else:
            time.sleep(args.interval)
