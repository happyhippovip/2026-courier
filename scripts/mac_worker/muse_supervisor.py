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

Usage: muse_supervisor.py start 1|4|8|16|32 [--allow-64] [--no-loop] | status |
       stop [--terminate] | resume SLOT
"""
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

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


def slot_home(slot_id):
    return WALL_DIR / "slots" / slot_id


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    tmp.replace(path)


def load_slots():
    return read_json(SLOTS_FILE, {})


def save_slots(slots):
    write_json(SLOTS_FILE, slots)


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
        if m is None:
            self.state = "HOLD"
            return self.admitted
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
        return self.admitted


def read_macos_metrics():
    try:
        swap = subprocess.check_output(["sysctl", "vm.swapusage"], text=True)
        load = subprocess.check_output(["sysctl", "vm.loadavg"], text=True)
        pressure = subprocess.check_output(["memory_pressure"], text=True)
        free = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure)
        used = re.search(r"used = ([\d.]+)M", swap)
        if not free or not used:
            return None
        return {"swap_mb": float(used.group(1)), "load_1m": float(re.findall(r"[\d.]+", load)[0]),
                "mem_free_pct": float(free.group(1))}
    except (OSError, subprocess.CalledProcessError, IndexError, ValueError):
        return None


class ProcessLauncher:
    """Detached daemon per slot (own session, cwd <slot>/work, log file; no terminal window)."""
    def __init__(self):
        self.children = {}

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
        return proc.pid

    def is_alive(self, slot_id, pid):
        proc = self.children.get(slot_id)
        if proc is not None and str(proc.pid) == str(pid):
            return proc.poll() is None
        if not pid:
            return False
        try:
            os.kill(int(pid), 0)
            return True
        except (OSError, ValueError):
            return False

    def exit_code(self, slot_id):
        try:
            return int((slot_home(slot_id) / "exit_code").read_text().strip())
        except (OSError, ValueError):
            return None

    def terminate(self, slot_id, pid):
        try:
            os.killpg(int(pid), signal.SIGTERM)
        except (OSError, ValueError):
            pass


def slot_env(slot_id, config):
    env = dict(os.environ)
    env.update({
        "COURIER_WORKER_HOME": str(slot_home(slot_id)),
        "COURIER_WORKER_ID": f"{config.get('worker_prefix', 'MUSE')}-{slot_id}",
        "COURIER_WORKER_ONE_TASK": "1",
        "COURIER_WORKER_DEFAULT_MODE": config.get("default_mode", "MUSE"),
    })
    if config.get("worker_config"):
        env["COURIER_WORKER_CONFIG"] = str(config["worker_config"])
    return env


class Supervisor:
    def __init__(self, launcher=None, governor=None, clock=time.time):
        self.launcher = launcher or ProcessLauncher()
        self.clock = clock
        config = read_json(CONFIG_FILE, {})
        self.gov = governor or CapacityGovernor(int(config.get("target", 4)), clock=clock)

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
        now = self.clock()
        slots = load_slots()
        config = read_json(CONFIG_FILE, {})
        stopping = STOP_FILE.exists()
        admitted = self.gov.evaluate(metrics)
        for slot in slots.values():
            if slot["state"] == RUNNING and not self.launcher.is_alive(slot["slot_id"], slot.get("pid")):
                self._on_exit(slot, now)
                if stopping:
                    slot["state"] = STOPPED
        active = sum(1 for s in slots.values() if s["state"] == RUNNING)
        for slot in sorted(slots.values(), key=lambda s: s["slot_id"]):
            if stopping or slot["state"] not in RUNNABLE or slot.get("backoff_until", 0) > now:
                continue
            if self.launcher.is_alive(slot["slot_id"], slot.get("pid")):
                slot["state"] = RUNNING  # adopt, never spawn a second daemon for a slot
                continue
            if active >= admitted or self.gov.state == "BACKOFF":
                slot["state"] = RESOURCE_BLOCKED
                continue
            pid = self.launcher.start(slot["slot_id"], slot_env(slot["slot_id"], config))
            slot.update(state=RUNNING, pid=pid, last_started_at=now, backoff_until=0)
            active += 1
        save_slots(slots)
        return slots


def acquire_lock():
    WALL_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_FILE, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def supervise(supervisor=None, interval=5.0):
    lock = acquire_lock()
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


def cmd_start(target, allow_64=False, loop=True):
    if target not in ALLOWED_TARGETS and not (allow_64 and target == 64):
        print(f"start supports {ALLOWED_TARGETS} (64 needs --allow-64)")
        return 2
    config = read_json(CONFIG_FILE, {})
    config["target"] = target
    write_json(CONFIG_FILE, config)
    STOP_FILE.unlink(missing_ok=True)
    slots = load_slots()
    for i in range(1, max(target, len(slots)) + 1):
        slot_id = f"{i:02d}"
        slot = slots.setdefault(slot_id, {"slot_id": slot_id, "state": STOPPED, "restart_count": 0, "crash_count": 0})
        if i <= target and slot["state"] == STOPPED:
            slot["state"] = IDLE
        elif i > target and slot["state"] != RUNNING:
            slot["state"] = STOPPED
    save_slots(slots)
    print(f"{target} slots enabled; ramp 1-4-8-16-32, resource-gated.")
    return supervise() if loop else 0


def cmd_stop(terminate=False, launcher=None):
    WALL_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text(str(time.time()))
    launcher = launcher or ProcessLauncher()
    slots = load_slots()
    for slot in slots.values():
        if slot["state"] == RUNNING:
            if terminate:
                launcher.terminate(slot["slot_id"], slot.get("pid"))
        else:
            slot["state"] = STOPPED
    save_slots(slots)
    print("STOP set: no new starts or restarts.")
    return 0


def cmd_resume(slot_id):
    slots = load_slots()
    slot = slots.get(slot_id)
    if not slot or slot["state"] != PAUSED_ERROR:
        print(f"{slot_id} is not PAUSED_ERROR.")
        return 1
    slot.update(state=IDLE, crash_count=0, blocker="")
    save_slots(slots)
    return 0


def cmd_status():
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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["start"] and len(argv) > 1:
        return cmd_start(int(argv[1]), "--allow-64" in argv, "--no-loop" not in argv)
    if argv[:1] == ["status"]:
        return cmd_status()
    if argv[:1] == ["stop"]:
        return cmd_stop("--terminate" in argv)
    if argv[:1] == ["resume"] and len(argv) > 1:
        return cmd_resume(argv[1])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
