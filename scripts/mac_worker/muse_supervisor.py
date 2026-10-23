#!/usr/bin/env python3
"""Muse slot supervisor on the canonical Courier worker path.

Each slot is one scripts/mac_worker/daemon.py process with its own home
(<wall>/slots/<SLOT>/), worker id and task state. The daemon does the Courier
work: /workers/register -> /tasks/claim -> current_task.json (CLAIMED /
STARTED / RESULT_READY) -> Muse via muse_adapter -> /tasks/result. It exits 0
after each delivered task (COURIER_WORKER_ONE_TASK=1). This supervisor only
keeps slots alive:

- a slot whose daemon exits is restarted after a short backoff; the daemon's
  persisted task state decides what happens next (RESULT_READY is re-sent,
  STARTED is released, never replayed; identities come from the server);
- fast non-zero exits back off exponentially and pause the slot
  (PAUSED_ERROR) after CRASH_LIMIT;
- one supervisor (file lock), one daemon per slot (pid check + the daemon's
  own state-dir lock);
- scale-up follows 1-4-8-16-32 only while resource metrics are readable and
  healthy. Nothing is killed except, on `stop --terminate`, this wall's own
  daemons.

Usage: muse_supervisor.py start 1|4|8|16|32 [--allow-64] [--no-loop] | status [--json] |
       build [1|4|8|16|32|64] | reconcile | notaus | bulletin |
       stop [--terminate] | resume SLOT|all | canary
"""
import fcntl
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_state import (CANONICAL_WORKSPACE, atomic_json, read_object, control_lock,
                           process_identity, same_process, cleanup_group, sync_directory,
                           group_exists)

WALL_DIR = Path(os.environ.get("COURIER_WALL_DIR", Path.home() / "Downloads" / "courier_work" / "muse_wall"))
SLOTS_FILE = WALL_DIR / "slots.json"
CONFIG_FILE = WALL_DIR / "config.json"
STOP_FILE = WALL_DIR / "STOP"
LOCK_FILE = WALL_DIR / "supervisor.lock"
DAEMON = Path(__file__).resolve().parent / "daemon.py"

ALLOWED_TARGETS = (1, 4, 8, 16, 32)
RAMP_LADDER = (1, 4, 8, 16, 32, 64)
RESTART_BACKOFF = 5.0
CRASH_BACKOFF_BASE = 15.0
CRASH_BACKOFF_MAX = 600.0
CRASH_LIMIT = 5
MIN_HEALTHY_RUNTIME = 60.0
RAMP_HOLD_SECONDS = 120.0

IDLE, RUNNING, BACKOFF = "IDLE", "RUNNING", "BACKOFF"
RESOURCE_BLOCKED, PAUSED_ERROR, STOPPED = "RESOURCE_BLOCKED", "PAUSED_ERROR", "STOPPED"
RUNNABLE = (IDLE, BACKOFF, RESOURCE_BLOCKED)
STARTING = "STARTING"


def slot_home(slot_id):
    return WALL_DIR / "slots" / slot_id


def read_json(path, default):
    return read_object(path, default)


def write_json(path, data):
    atomic_json(path, data)


def load_slots():
    return read_json(SLOTS_FILE, {})


def save_slots(slots):
    write_json(SLOTS_FILE, slots)
    for slot_id, slot in slots.items():
        try:
            home = slot_home(slot_id)
            home.mkdir(parents=True, exist_ok=True)
            state_data = {
                "slot_id": f"MUSE-{slot_id}",
                "state": slot.get("state"),
                "process": slot.get("pid"),
                "updated_at": slot.get("last_started_at") or slot.get("updated_at") or time.time(),
                "workdir": str(home / "work"),
            }
            write_json(home / "state.json", state_data)
        except OSError:
            pass


def worker_view(slot_id):
    """Read-only view of the slot's canonical worker state."""
    state = slot_home(slot_id) / "state"
    task = read_json(state / "current_task.json", {})
    ckpt = read_json(state / "checkpoint.json", {})
    return {"task_id": task.get("task_id") or ckpt.get("task_id") or "",
            "phase": task.get("worker_phase", "") if task else "",
            "branch": ckpt.get("branch", ""), "last_commit": ckpt.get("last_commit", ""),
            "next_task": ckpt.get("next_task", "")}


class CapacityGovernor:
    """Ramp 1-4-8-16-32(-64); unreadable metrics hold (fail closed)."""
    def __init__(self, requested_max=4, clock=time.time, reader=None):
        self.requested_max = requested_max
        self.admitted = min(1, requested_max)
        self.state = "HOLD"
        self.clock = clock
        self.level_since = clock()
        self.last = None
        self.reader = reader or read_macos_metrics

    def _ladder(self):
        ladder = [c for c in RAMP_LADDER if c <= self.requested_max]
        if self.requested_max not in ladder:
            ladder.append(self.requested_max)
        return ladder

    def evaluate(self, metrics="read"):
        m = self.reader() if metrics == "read" else metrics
        if (not isinstance(m, dict) or any(
                isinstance(m.get(k), bool) or not isinstance(m.get(k), (int, float))
                or not math.isfinite(m[k]) for k in ("swap_mb", "load_1m", "mem_free_pct"))):
            m = None
        if m is None:
            self.state = "HOLD"
            self.level_since = self.clock()
            self.last = None
            return 0  # Historical capacity never authorizes new work without metrics.
        if self.last is None:
            self.level_since = self.clock()
        prev = self.last or m
        d_swap = m["swap_mb"] - prev["swap_mb"]
        if d_swap > 500 or m["load_1m"] > 10.0 or m["mem_free_pct"] < 10.0:
            self.state = "BACKOFF"
            smaller = [c for c in self._ladder() if c < self.admitted]
            self.admitted = smaller[-1] if smaller else self.admitted
            self.level_since = self.clock()
        elif d_swap > 100 or m["load_1m"] > 5.0 or m["mem_free_pct"] < 25.0:
            self.state = "HOLD"
            self.level_since = self.clock()
        else:
            self.state = "RAMPING"
            if self.admitted < self.requested_max and self.clock() - self.level_since >= RAMP_HOLD_SECONDS:
                self.admitted = [c for c in self._ladder() if c > self.admitted][0]
                self.level_since = self.clock()
        self.last = m
        return self.admitted if self.state == "RAMPING" else 0


def read_macos_metrics():
    try:
        swap = subprocess.check_output(["sysctl", "vm.swapusage"], text=True, timeout=2)
        load = subprocess.check_output(["sysctl", "vm.loadavg"], text=True, timeout=2)
        pressure = subprocess.check_output(["memory_pressure"], text=True, timeout=2)
        free = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure)
        used = re.search(r"used = ([\d.]+)M", swap)
        load_m = re.search(r"\{\s*([\d.]+)", load)
        if not free or not used or not load_m:
            return None
        return {"swap_mb": float(used.group(1)), "load_1m": float(load_m.group(1)),
                "mem_free_pct": float(free.group(1))}
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return None


class ProcessLauncher:
    """Detached daemon per slot (own session, cwd <slot>/work, log file; no terminal window)."""
    def __init__(self):
        self.children = {}
        self.identities = {}

    def start(self, slot_id, env):
        home = slot_home(slot_id)
        (home / "logs").mkdir(parents=True, exist_ok=True)
        (home / "work").mkdir(parents=True, exist_ok=True)
        exit_file = home / "exit_code"
        exit_file.unlink(missing_ok=True)
        cmd = f'"{sys.executable}" "{DAEMON}"; echo $? > "{exit_file}"'
        with open(home / "logs" / "slot.out", "a") as out:
            proc = subprocess.Popen(["bash", "-c", cmd], env=env, stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True, cwd=home / "work")
        self.children[slot_id] = proc
        self.identities[slot_id] = process_identity(proc.pid)
        return proc.pid

    def identity(self, slot_id):
        return self.identities.get(slot_id)

    def owned(self, slot_id, pid, identity):
        proc = self.children.get(slot_id)
        if proc is not None and str(proc.pid) == str(pid):
            return proc.poll() is None
        return same_process(pid, identity) if pid else False

    def is_alive(self, slot_id, pid):
        proc = self.children.get(slot_id)
        if proc is not None and str(proc.pid) == str(pid):
            return proc.poll() is None
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False

    def exit_code(self, slot_id):
        try:
            return int((slot_home(slot_id) / "exit_code").read_text().strip())
        except (OSError, ValueError):
            return None

    def terminate(self, slot_id, pid, identity=None):
        identity = identity or self.identities.get(slot_id)
        if not self.owned(slot_id, pid, identity):
            return False
        proc = self.children.get(slot_id)
        if proc is None:
            class Recovered:
                def __init__(self, value):
                    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                        raise ValueError("pid is not a process id. Bool is not a number.")
                    self.pid = value
                    self.returncode = None
                    self._recovered = True
                def poll(self):
                    if self.returncode is not None:
                        return self.returncode
                    try:
                        pid, status = os.waitpid(self.pid, os.WNOHANG)
                        if pid == self.pid:
                            self.returncode = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else (status >> 8)
                            return self.returncode
                    except (ChildProcessError, OSError):
                        pass
                    if not group_exists(self.pid):
                        self.returncode = 0
                        return self.returncode
                    return None
            proc = Recovered(pid)
        return cleanup_group(proc, identity)


def slot_env(slot_id, config):
    env = dict(os.environ)
    env.update({
        "COURIER_WORKER_HOME": str(slot_home(slot_id)),
        "COURIER_WORKER_ID": f"{config.get('worker_prefix', 'MUSE')}-{slot_id}",
        "COURIER_WORKER_ONE_TASK": "1",
        "COURIER_WORKER_DEFAULT_MODE": config.get("default_mode", "MUSE"),
        "COURIER_SLOT_ID": slot_id,
        "COURIER_WALL_DIR": str(WALL_DIR.resolve()),
        "COURIER_MUSE_WORKSPACE": config.get("workspace", CANONICAL_WORKSPACE),
    })
    if config.get("worker_config"):
        env["COURIER_WORKER_CONFIG"] = str(Path(config["worker_config"]).expanduser().resolve())
    return env


class Supervisor:
    def __init__(self, launcher=None, governor=None, clock=time.time):
        self.launcher = launcher or ProcessLauncher()
        self.clock = clock
        config = read_json(CONFIG_FILE, {})
        raw_target = config.get("target", 4)
        if isinstance(raw_target, bool) or not isinstance(raw_target, int):
            raise ValueError("target is not a slot count. Bool is not a number.")
        self.gov = governor or CapacityGovernor(raw_target, clock=clock)

    def _on_exit(self, slot, now):
        code = self.launcher.exit_code(slot["slot_id"])
        runtime = now - slot.get("last_started_at", now)
        slot.update(pid="", last_exit_code=code, last_finished_at=now,
                    restart_count=slot.get("restart_count", 0) + 1)
        if code != 0 and runtime < MIN_HEALTHY_RUNTIME:
            slot["crash_count"] = slot.get("crash_count", 0) + 1
            if slot["crash_count"] >= CRASH_LIMIT:
                slot.update(state=PAUSED_ERROR, backoff_until=0,
                            blocker=f"{slot['crash_count']} fast exits in a row (last exit {code})")
                return
            delay = min(CRASH_BACKOFF_BASE * 2 ** (slot["crash_count"] - 1), CRASH_BACKOFF_MAX)
            slot.update(state=BACKOFF, backoff_until=now + delay)
        else:
            slot.update(state=BACKOFF, backoff_until=now + RESTART_BACKOFF, crash_count=0, blocker="")

    def tick(self, metrics="read"):
        # Potentially slow metrics happen before the lock; STOP is rechecked inside.
        admitted = self.gov.evaluate(metrics)
        with control_lock(WALL_DIR):
            return self._tick(admitted)

    def _alive(self, slot):
        if hasattr(self.launcher, "owned"):
            return self.launcher.owned(slot["slot_id"], slot.get("pid"), slot.get("process_identity"))
        return self.launcher.is_alive(slot["slot_id"], slot.get("pid"))

    def _tick(self, admitted):
        now = self.clock()
        slots = load_slots()
        config = read_json(CONFIG_FILE, {})
        stopping = STOP_FILE.exists()
        for slot in slots.values():
            if slot["state"] == STARTING:
                slot.update(state=PAUSED_ERROR, blocker="UNCERTAIN_SPAWN: reconcile slot worker before resume")
            if slot["state"] == RUNNING and not self._alive(slot):
                if slot.get("pid") and self.launcher.is_alive(slot["slot_id"], slot.get("pid")):
                    slot.update(state=PAUSED_ERROR, blocker="PROCESS_IDENTITY_MISMATCH")
                    continue
                self._on_exit(slot, now)
                if stopping:
                    slot["state"] = STOPPED
        active = sum(1 for s in slots.values() if s["state"] == RUNNING)
        new_starts = 0
        for slot in sorted(slots.values(), key=lambda s: s["slot_id"]):
            if stopping or slot["state"] not in RUNNABLE or slot.get("backoff_until", 0) > now:
                continue
            if self._alive(slot):
                slot["state"] = RUNNING  # adopt, never spawn a second daemon for a slot
                active += 1
                continue
            if active >= admitted or self.gov.state != "RAMPING" or new_starts >= 1:
                slot["state"] = RESOURCE_BLOCKED
                continue
            slot.update(state=STARTING, workspace=config.get("workspace", CANONICAL_WORKSPACE))
            save_slots(slots)  # A crash after this point cannot blindly respawn this slot.
            pid = self.launcher.start(slot["slot_id"], slot_env(slot["slot_id"], config))
            slot.update(state=RUNNING, pid=pid, last_started_at=now, backoff_until=0)
            if hasattr(self.launcher, "identity"):
                slot["process_identity"] = self.launcher.identity(slot["slot_id"])
            save_slots(slots)
            active += 1
            new_starts += 1
        save_slots(slots)
        return slots


_supervisor_lease_store = None


def get_authority_store():
    global _supervisor_lease_store
    if _supervisor_lease_store is None:
        try:
            from courier_runtime.lease import LeaseStore
            auth_db = WALL_DIR / "authority.db"
            _supervisor_lease_store = LeaseStore(str(auth_db))
        except Exception:
            _supervisor_lease_store = None
    return _supervisor_lease_store


class SupervisorLock:
    def __init__(self, handle, lease, store):
        self.handle = handle
        self.lease = lease
        self.store = store

    def close(self):
        if self.lease and self.store:
            try:
                self.store.release(self.lease)
            except Exception:
                pass
            self.lease = None
        if self.handle:
            try:
                fcntl.flock(self.handle, fcntl.LOCK_UN)
                self.handle.close()
            except Exception:
                pass
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def acquire_lock():
    if WALL_DIR.is_symlink() or WALL_DIR.parent.is_symlink():
        raise OSError(f"{WALL_DIR}: refusing to follow a symlink")
    lock_path = Path(LOCK_FILE)
    if lock_path.is_symlink() or lock_path.parent.is_symlink():
        raise OSError(f"{lock_path}: refusing to follow a symlink")
    WALL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        handle = open(LOCK_FILE, "w")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None

    # Acquire canonical writer lease in authority.db
    store = get_authority_store()
    lease = None
    if store is not None:
        try:
            from courier_runtime.lease import format_session_holder
            import psutil
            holder = format_session_holder("mac_supervisor", os.getpid(), psutil.Process(os.getpid()).create_time(), str(uuid.uuid4()))
            lease = store.acquire("supervisor:mac_wall", holder, "supervise", ttl_s=3600)
        except Exception:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
                handle.close()
            except Exception:
                pass
            return None
    return SupervisorLock(handle, lease, store)


def supervise(supervisor=None, interval=5.0, lock=None):
    lock = lock or acquire_lock()
    if lock is None:
        print("Another Muse supervisor is running; not starting a second one.")
        return 1

    sup = supervisor or Supervisor()
    while True:
        slots = sup.tick()
        active = sum(1 for s in slots.values() if s["state"] == RUNNING)
        if STOP_FILE.exists() and active == 0:
            return 0
        time.sleep(interval)


def cmd_build(target=4, workspace=None):
    """WALL-AUFBAUEN: Initialises slot directories, config, and slot records without starting workers."""
    if isinstance(target, bool) or (target not in ALLOWED_TARGETS and target != 64):
        print(f"build supports {ALLOWED_TARGETS}")
        return 2
    with control_lock(WALL_DIR):
        WALL_DIR.mkdir(parents=True, exist_ok=True)
        config = read_json(CONFIG_FILE, {})
        ws = workspace or config.get("workspace", CANONICAL_WORKSPACE)
        config.update(target=target, workspace=ws)
        write_json(CONFIG_FILE, config)
        slots = load_slots()
        for i in range(1, target + 1):
            slot_id = f"{i:02d}"
            home = slot_home(slot_id)
            for sub in ("work", "logs", "state"):
                (home / sub).mkdir(parents=True, exist_ok=True)
            slot = slots.setdefault(slot_id, {
                "slot_id": slot_id,
                "state": STOPPED,
                "restart_count": 0,
                "crash_count": 0,
            })
            slot["workspace"] = ws
            if slot.get("state") not in (RUNNING, BACKOFF, PAUSED_ERROR):
                slot["state"] = IDLE
        save_slots(slots)
        print(f"WALL-AUFBAUEN: {target} slots initialised in {WALL_DIR}.")
        return 0


def cmd_reconcile(launcher=None):
    """WALL-ORDNEN: Cleans up orphaned processes, reconciles slot state with process table."""
    launcher = launcher or ProcessLauncher()
    with control_lock(WALL_DIR):
        slots = load_slots()
        changed = False
        for slot_id, slot in slots.items():
            pid = slot.get("pid")
            identity = slot.get("process_identity")
            state = slot.get("state")
            if pid:
                is_alive = launcher.is_alive(slot_id, pid)
                is_owned = launcher.owned(slot_id, pid, identity)
                if not is_alive or not is_owned:
                    launcher.terminate(slot_id, pid, identity)
                    slot["pid"] = None
                    slot["process_identity"] = None
                    exit_code = launcher.exit_code(slot_id)
                    slot["last_exit_code"] = exit_code
                    if state in (RUNNING, STARTING):
                        slot["state"] = IDLE if exit_code == 0 else PAUSED_ERROR
                        if exit_code != 0 and not slot.get("blocker"):
                            slot["blocker"] = f"ORPHANED_CLEANUP: process {pid} exited with {exit_code}"
                    changed = True
            elif state == RUNNING:
                slot["state"] = IDLE
                changed = True
            if not slot.get("pid") and slot.get("blocker", "").startswith("CLEANUP_NOT_PROVEN"):
                slot["blocker"] = ""
                changed = True
        if changed:
            save_slots(slots)
        print("WALL-ORDNEN: Process table and slot records reconciled.")
        return 0


def cmd_notaus(launcher=None):
    """WALL-NOTAUS: Immediate cancellation of all slot processes (SIGKILL fallback via terminate=True)."""
    print("WALL-NOTAUS triggered: Terminating all slot processes immediately.")
    return cmd_stop(terminate=True, launcher=launcher)


def cmd_start(target, allow_64=False, loop=True):
    if isinstance(target, bool) or (target not in ALLOWED_TARGETS and not (allow_64 and target == 64)):
        print(f"start supports {ALLOWED_TARGETS} (64 needs --allow-64)")
        return 2
    lock = acquire_lock()
    if lock is None:
        print("Another Muse supervisor is running; no state changed.")
        return 1
    try:
        with control_lock(WALL_DIR):
            if STOP_FILE.exists():
                print("STOP remains authoritative; use explicit resume all before start.")
                return 1
            config = read_json(CONFIG_FILE, {})
            config.update(target=target, workspace=config.get("workspace", CANONICAL_WORKSPACE))
            write_json(CONFIG_FILE, config)
            slots = load_slots()
            for i in range(1, max(target, len(slots)) + 1):
                slot_id = f"{i:02d}"
                slot = slots.setdefault(slot_id, {"slot_id": slot_id, "state": STOPPED, "restart_count": 0, "crash_count": 0})
                slot.setdefault("workspace", config["workspace"])
                if i <= target and slot["state"] == STOPPED:
                    slot["state"] = IDLE
                elif i > target and slot["state"] != RUNNING:
                    slot["state"] = STOPPED
            save_slots(slots)
        print(f"{target} slots enabled; resource-gated, at most one new worker per tick.")
        return supervise(lock=lock) if loop else 0
    except KeyboardInterrupt:
        cmd_stop(terminate=True)
        return 130
    finally:
        lock.close()


def cmd_stop(terminate=False, launcher=None):
    with control_lock(WALL_DIR):
        return _stop(terminate, launcher)


def _stop(terminate=False, launcher=None):
    WALL_DIR.mkdir(parents=True, exist_ok=True)
    atomic_json(STOP_FILE, {"stopped_at": time.time()})
    launcher = launcher or ProcessLauncher()
    slots = load_slots()
    for slot in slots.values():
        if terminate and slot.get("pid"):
            if not launcher.terminate(slot["slot_id"], slot.get("pid"), slot.get("process_identity")):
                slot["blocker"] = "CLEANUP_NOT_PROVEN: reconcile owned processes"
            else:
                slot["pid"] = None
        if terminate or slot["state"] != RUNNING:
            slot["state"] = STOPPED
    save_slots(slots)
    print("STOP set: no new starts or restarts.")
    return 0


def cmd_resume(slot_id):
    with control_lock(WALL_DIR):
        if slot_id == "all":
            STOP_FILE.unlink(missing_ok=True)
            sync_directory(WALL_DIR)
            print("STOP explicitly cleared; start N may now enable stopped slots.")
            return 0
        return _resume_slot(slot_id)


def _resume_slot(slot_id):
    slots = load_slots()
    slot = slots.get(slot_id)
    if not slot or slot["state"] != PAUSED_ERROR:
        print(f"{slot_id} is not PAUSED_ERROR.")
        return 1
    if slot.get("blocker", "").startswith(("UNCERTAIN_SPAWN", "PROCESS_IDENTITY", "CLEANUP")):
        print("Reconciliation required; unsafe ownership cannot be reset by resume.")
        return 1
    slot.update(state=IDLE, crash_count=0, blocker="")
    save_slots(slots)
    return 0


def cmd_status(as_json=False):
    if as_json:
        slots = load_slots()
        models = [slot_model(sid) for sid in sorted(slots.keys())]
        print(json.dumps(models, indent=2))
        return 0
    config = read_json(CONFIG_FILE, {})
    print(f"target={config.get('target', 4)}{' STOP' if STOP_FILE.exists() else ''}")
    print("slot\tstate\ttask\tphase\tbranch\tlast_commit\texit\trestarts\tcrashes\tnext")
    for slot_id, slot in sorted(load_slots().items()):
        if slot["state"] == STOPPED:
            continue
        w = worker_view(slot_id)
        print("\t".join(str(v) for v in (slot_id, slot["state"], w["task_id"] or "-", w["phase"] or "-",
                                         w["branch"] or "-", (w["last_commit"] or "-")[:10],
                                         slot.get("last_exit_code", "-"), slot.get("restart_count", 0),
                                         slot.get("crash_count", 0), w["next_task"] or "-")))
    return 0


def slot_model(slot_id):
    """Formats a single slot into the 12 canonical fields required by Section E."""
    slots = load_slots()
    slot_data = slots.get(slot_id, {})
    wv = worker_view(slot_id)
    state = slot_data.get("state", "UNKNOWN")
    pid = slot_data.get("pid")

    if not pid:
        proc_status = "NONE"
    else:
        proc_status = "ALIVE" if state == RUNNING else "REAPED"

    backoff_until = slot_data.get("backoff_until", 0)
    now = time.time()
    backoff_remaining = max(0, int(backoff_until - now)) if backoff_until > now else 0
    backoff_str = f"{backoff_remaining}s" if backoff_remaining > 0 else "NONE"

    return {
        "SLOT_ID": slot_id,
        "HOST": slot_data.get("host") or "mac-antigravity",
        "AGENT": slot_data.get("agent") or "MUSE",
        "PROCESS_STATUS": proc_status,
        "CURRENT_WORKKEY": wv.get("task_id") or "UNKNOWN",
        "OWNER": slot_data.get("owner") or "happyhippovip",
        "LEASE": slot_data.get("lease") or ("ACTIVE" if state == RUNNING else "EXPIRED"),
        "LAST_ACTIVITY": slot_data.get("last_started_at") or slot_data.get("updated_at") or "UNKNOWN",
        "BACKOFF": backoff_str,
        "RESOURCE_STATUS": slot_data.get("resource_status") or "NORMAL",
        "SOURCE_PROVENANCE": slot_data.get("source_provenance") or "scripts/mac_worker/muse_supervisor.py",
        "VERIFICATION_STATUS": wv.get("next_task") or "PENDING",
    }


def bulletin_feed():
    """Deterministic, zero-token bulletin generator per Section F."""
    slots = load_slots()
    models = [slot_model(sid) for sid in sorted(slots.keys())]
    events = []
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if STOP_FILE.exists():
        events.append({
            "timestamp": now_iso,
            "level": "CRITICAL",
            "code": "RESOURCE_PAUSE_ACTIVE",
            "message": "RESOURCE_PAUSE ist aktiv: Not-Aus STOP Datei sperrt alle Slots."
        })

    for s in models:
        slot_id = s["SLOT_ID"]
        state = s["PROCESS_STATUS"]
        backoff = s["BACKOFF"]
        workkey = s["CURRENT_WORKKEY"]
        lease = s["LEASE"]
        verif = s["VERIFICATION_STATUS"]

        if state == "ALIVE":
            events.append({
                "timestamp": now_iso,
                "level": "INFO",
                "code": "SLOT_RUNNING",
                "message": f"Slot {slot_id} wurde nachweisbar gestartet (Workkey: {workkey})."
            })
        elif backoff != "NONE":
            events.append({
                "timestamp": now_iso,
                "level": "WARN",
                "code": "SLOT_BACKOFF",
                "message": f"Slot {slot_id} befindet sich im Backoff ({backoff} verbleibend)."
            })
        elif state == "NONE":
            events.append({
                "timestamp": now_iso,
                "level": "INFO",
                "code": "SLOT_WAITING",
                "message": f"Slot {slot_id} wartet auf autorisierte Arbeitszuteilung."
            })

        if lease != "ACTIVE" and workkey != "UNKNOWN":
            events.append({
                "timestamp": now_iso,
                "level": "ERROR",
                "code": "LEASE_INVALID",
                "message": f"Workkey {workkey} an Slot {slot_id} besitzt keinen gültigen Lease."
            })

        if verif == "PENDING" and workkey != "UNKNOWN":
            events.append({
                "timestamp": now_iso,
                "level": "INFO",
                "code": "VERIFIER_PENDING",
                "message": f"Verifier-Ergebnis für Workkey {workkey} steht aus."
            })

    metrics = read_macos_metrics()
    if metrics and metrics.get("load_1m", 0) > 10.0:
        events.append({
            "timestamp": now_iso,
            "level": "WARN",
            "code": "HOST_PRESSURE_HIGH",
            "message": f"Hoststatus unter Druck: Load-1m bei {metrics.get('load_1m')}."
        })

    return events


def cmd_bulletin():
    events = bulletin_feed()
    for e in events:
        print(f"[{e['timestamp']}] [{e['level']}] [{e['code']}] {e['message']}")
    return 0


def cmd_canary():
    """One logical slot, one bounded Muse exec, no queue or Keychain access.

    Durable STARTED is never retried; RESULT_READY is displayed, never recomputed.
    This exercises the exact production adapter/run_muse boundary, not a second wall.
    """
    import daemon
    lock = acquire_lock()
    if lock is None:
        print("Supervisor already active; canary refused.")
        return 1
    home = WALL_DIR / "canary" / "01"
    previous_env = {k: os.environ.get(k) for k in
                    ("COURIER_WALL_DIR", "COURIER_SLOT_ID", "COURIER_MUSE_WORKSPACE", "COURIER_MUSE_CLI")}
    previous_state, previous_logs = daemon.STATE_DIR, daemon.LOGS_DIR
    try:
        with control_lock(WALL_DIR):
            if STOP_FILE.exists():
                print("STOP present; canary refused. Only explicit resume all may clear it.")
                return 1
            if any(slot.get("pid") or slot.get("state") == STARTING for slot in load_slots().values()):
                print("Existing slot ownership must be reconciled before the single canary.")
                return 1
            path = home / "state" / "current_task.json"
            task = read_object(path)
            if task.get("worker_phase") == "RESULT_READY":
                print("Canary already completed; no reexecution.")
                return 0 if task["result_payload"].get("status") == "SUCCESS" else 1
            if task and task.get("worker_phase") != "CLAIMED":
                print("Canary execution ambiguous; reconcile before any further run.")
                return 1
            if CapacityGovernor(1).evaluate() == 0:
                print("No safe resource admission; zero Muse starts.")
                return 1
            task = task or {"goal_id": "physical-muse-canary", "task_id": "physical-muse-canary-01",
                "attempt_id": "physical-muse-canary-01:attempt:1", "dispatch_id": "physical-muse-canary-01:dispatch:1",
                "worker_id": "MUSE-CANARY-01", "mode": "MUSE", "muse_action": "exec",
                "instruction": "Connectivity canary only. Do not modify files, run tools, contact other services, "
                               "or start other jobs. Reply with a fenced JSON object containing status SUCCESS "
                               "and next_task CANARY_OK. Do not invent a session reference."}
            task["worker_phase"] = "STARTED"
            atomic_json(path, task)
        daemon.STATE_DIR, daemon.LOGS_DIR = home / "state", home / "logs"
        daemon.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        os.environ.update(COURIER_WALL_DIR=str(WALL_DIR.resolve()), COURIER_SLOT_ID="01",
                          COURIER_MUSE_WORKSPACE=CANONICAL_WORKSPACE)
        # Operator-confirmed commands only. Do not inherit an arbitrary CLI/test binary.
        os.environ["COURIER_MUSE_CLI"] = json.dumps({"protocol": "headless-v1"})
        config = {"WORKER_ID": "MUSE-CANARY-01", "MUSE_TIMEOUT_SECONDS": 60}
        try:
            result = daemon.run_muse(task, config)
        except daemon.MuseAdmissionBlocked:
            atomic_json(path, dict(task, worker_phase="CLAIMED"))
            print("Admission withdrawn before launch; no Muse execution.")
            return 1
        atomic_json(path, dict(task, worker_phase="RESULT_READY", result_payload=result))
        import muse_adapter
        muse_adapter.save_checkpoint(daemon.STATE_DIR, task, result, slot_id="01", workspace=CANONICAL_WORKSPACE)
        print(f"CANARY_STATUS={result.get('status')} OUTPUT_DIR={daemon.STATE_DIR}")
        return 0 if result.get("status") == "SUCCESS" else 1
    finally:
        daemon.STATE_DIR, daemon.LOGS_DIR = previous_state, previous_logs
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        lock.close()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else ""
    if cmd in ("build", "wall-aufbauen"):
        target = int(argv[1]) if len(argv) > 1 else 4
        return cmd_build(target)
    if cmd in ("reconcile", "wall-ordnen"):
        return cmd_reconcile()
    if cmd in ("start", "wall-starten") and len(argv) > 1:
        return cmd_start(int(argv[1]), "--allow-64" in argv, "--no-loop" not in argv)
    if cmd in ("status", "wall-status"):
        return cmd_status(as_json="--json" in argv)
    if cmd in ("bulletin", "wall-bulletin"):
        return cmd_bulletin()
    if cmd in ("canary", "wall-canary"):
        return cmd_canary()
    if cmd in ("notaus", "wall-notaus"):
        return cmd_notaus()
    if cmd in ("stop", "wall-stoppen"):
        return cmd_stop("--terminate" in argv)
    if cmd in ("resume", "wall-resume") and len(argv) > 1:
        return cmd_resume(argv[1])
    print(__doc__)
    return 1


if __name__ == "__main__":
    def shutdown(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, shutdown)
    sys.exit(main())
