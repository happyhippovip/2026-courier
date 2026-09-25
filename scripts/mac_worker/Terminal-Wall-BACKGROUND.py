#!/usr/bin/env python3
"""Courier Terminal Wall (background): slot supervisor on state.tsv.

Slots run detached in `screen` (no Terminal windows). state.tsv is the one
slot state/checkpoint; claims/<slot>/ holds owner.txt, the exit_code the
wrapper writes, and an optional checkpoint.json the worker writes
({"branch", "last_commit", "next_task", "proof_ref"}).

Controller:
  start N [--allow-64] [--no-loop]   enable the first N slots (4/8/16/32), supervise
  status                             one line per enabled slot + governor
  stop [--terminate]                 no further starts/restarts; --terminate also
                                     quits this wall's own screen sessions
  resume SLOT                        clear PAUSED_ERROR on one slot
Legacy: dashboard | attach SLOT | supervise [--once] | canary [--once] | profile P [N]

A worker that exits is restarted in the same slot with the same task after a
short backoff. Fast non-zero exits count as crashes (exponential backoff,
PAUSED_ERROR at CRASH_LIMIT). Scale-up follows the ladder 1-4-8-16-32(-64) and
only while CapacityGovernor reports healthy metrics; missing metrics hold.
Nothing here kills a process it did not start.
"""
import os, sys, subprocess, csv, time, re, json, fcntl, shlex
from datetime import datetime

WALL_DIR = os.environ.get("COURIER_WALL_DIR", os.path.expanduser("~/Downloads/courier_work/wall"))
STATE_FILE = os.path.join(WALL_DIR, "state.tsv")
CLAIMS_DIR = os.path.join(WALL_DIR, "claims")
CONFIG_FILE = os.path.join(WALL_DIR, "capacity_profile.json")
STOP_FILE = os.path.join(WALL_DIR, "STOP")
LOCK_FILE = os.path.join(WALL_DIR, "supervisor.lock")
QUEUE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work_queue.py")
QUEUE_DIR = os.environ.get("COURIER_QUEUE_DIR", "/tmp/courier_work_queue")

# Existing generate_wall_state.py columns first, then the checkpoint columns.
FIELDS = ["slot_id", "wid", "worker_type", "account_provider", "task_id", "scope", "state",
          "claim_created_at", "pid", "pty", "proof_ref", "next_action", "blocker", "updated_at",
          "branch", "last_commit", "next_task", "last_exit_code", "restart_count", "crash_count",
          "task_restarts", "last_started_at", "last_finished_at", "backoff_until"]

ALLOWED_TARGETS = (4, 8, 16, 32)
RAMP_LADDER = (1, 4, 8, 16, 32, 64)
RESTART_BACKOFF = 5.0          # seconds after a normal exit
CRASH_BACKOFF_BASE = 15.0      # first fast-crash backoff, doubles per crash
CRASH_BACKOFF_MAX = 600.0
CRASH_LIMIT = 5                # consecutive fast crashes -> PAUSED_ERROR
MIN_HEALTHY_RUNTIME = 60.0     # shorter non-zero runs are crashes
TASK_RESTART_LIMIT = 10        # restarts of one task without proof -> block task
RATE_LIMIT_EXIT = 75           # EX_TEMPFAIL: worker reports a provider rate limit
RATE_LIMIT_BACKOFF = 900.0
RAMP_HOLD_SECONDS = 120.0      # healthy time at one level before the next step

# Slot states. WORKING is the running state (legacy name, kept for the dashboard).
IDLE, WAITING, WORKING, BACKOFF, RATE_LIMITED = "IDLE", "WAITING", "WORKING", "BACKOFF", "RATE_LIMITED"
RESOURCE_BLOCKED, PAUSED_ERROR, STOPPED = "RESOURCE_BLOCKED", "PAUSED_ERROR", "STOPPED"
RUNNABLE = (IDLE, WAITING, BACKOFF, RATE_LIMITED, RESOURCE_BLOCKED)


def now_iso(t=None):
    return datetime.fromtimestamp(t if t is not None else time.time()).isoformat()


# --- CUSTOMER WORKER CAPACITY PROFILE ---
def load_capacity_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"profile": "AUTO", "custom_max": 4}

def get_requested_max(config):
    p = config.get("profile", "AUTO")
    if p == "LOW": return 8
    if p == "MEDIUM": return 32
    if p == "HIGH": return 64
    if p == "CUSTOM": return int(config.get("custom_max", 4))
    return 4 # AUTO: safe default; larger walls are an explicit start N


class CapacityGovernor:
    def __init__(self, requested_max=4, start_capacity=1, clock=time.time):
        self.requested_max = requested_max
        self.admitted_capacity = min(start_capacity, requested_max)
        self.state = "RAMPING"
        self.last_metrics = None
        self.timeout_count = 0
        self.resource_health = "UNKNOWN"
        self.clock = clock
        self.level_since = clock()

    def get_real_metrics(self):
        """macOS metrics. Returns None when they cannot be read (fail closed)."""
        m = {"swap_mb": 0.0, "load_1m": 0.0, "free_pages": 0, "ws_cpu": 0.0, "term_cpu": 0.0, "worker_rss_mb": 0.0, "active_procs": 0, "mem_pressure_pct": None, "sys_latency_ms": 0.0}
        try:
            swap_out = subprocess.check_output(["sysctl", "vm.swapusage"]).decode()
            match = re.search(r'used = ([\d\.]+)M', swap_out)
            if match: m["swap_mb"] = float(match.group(1))

            load_out = subprocess.check_output(["sysctl", "vm.loadavg"]).decode()
            m["load_1m"] = float(re.findall(r'[\d\.]+', load_out)[0])

            vmstat = subprocess.check_output(["vm_stat"]).decode()
            for line in vmstat.split('\n'):
                if "Pages free" in line:
                    m["free_pages"] = int(line.split(':')[1].strip().strip('.'))

            mp_out = subprocess.check_output(["memory_pressure"]).decode()
            mp_match = re.search(r'System-wide memory free percentage:\s*([\d]+)%', mp_out)
            if not mp_match:
                return None
            m["mem_pressure_pct"] = float(mp_match.group(1))

            ps_out = subprocess.check_output(["ps", "-A", "-o", "%cpu,rss,command"]).decode()
            procs = ps_out.strip().split('\n')[1:]
            m["active_procs"] = len(procs)
            for line in procs:
                parts = line.strip().split(maxsplit=2)
                if len(parts) < 3: continue
                cpu, rss, cmd = float(parts[0]), float(parts[1])/1024.0, parts[2]
                if "WindowServer" in cmd: m["ws_cpu"] += cpu
                if "Terminal.app" in cmd: m["term_cpu"] += cpu
                if "muse --yolo" in cmd or "agy" in cmd: m["worker_rss_mb"] += rss

            t0 = time.time()
            subprocess.run(["ping", "-c", "1", "-t", "1", "127.0.0.1"], stdout=subprocess.DEVNULL)
            m["sys_latency_ms"] = (time.time() - t0) * 1000.0
        except Exception:
            return None
        return m

    def _step(self, direction):
        ladder = [c for c in RAMP_LADDER if c <= self.requested_max] or [self.requested_max]
        if self.requested_max not in ladder: ladder.append(self.requested_max)
        if direction > 0:
            bigger = [c for c in ladder if c > self.admitted_capacity]
            if bigger: self.admitted_capacity = bigger[0]
        else:
            smaller = [c for c in ladder if c < self.admitted_capacity]
            self.admitted_capacity = smaller[-1] if smaller else ladder[0]
        self.level_since = self.clock()

    def evaluate(self, metrics="read"):
        curr = self.get_real_metrics() if metrics == "read" else metrics
        if curr is None:
            # No readable metrics: never scale up, never scale down running work.
            self.state, self.resource_health = "HOLD", "UNKNOWN"
            return self.admitted_capacity
        self.admitted_capacity = min(self.admitted_capacity, self.requested_max)
        prev = self.last_metrics or curr
        d_swap = curr["swap_mb"] - prev["swap_mb"]
        d_ws = curr["ws_cpu"] - prev["ws_cpu"]
        d_lat = curr["sys_latency_ms"] - prev["sys_latency_ms"]
        if d_swap > 500 or curr["load_1m"] > 10.0 or curr["mem_pressure_pct"] < 10.0 or curr["sys_latency_ms"] > 1000.0 or self.timeout_count > 3:
            self.state = "BACKOFF"
            self.resource_health = "CRITICAL"
            self._step(-1)
            self.timeout_count = 0
        elif d_swap > 100 or curr["load_1m"] > 5.0 or curr["mem_pressure_pct"] < 25.0 or curr["ws_cpu"] > 60.0 or d_ws > 20.0 or d_lat > 100.0:
            self.state = "HOLD"
            self.resource_health = "STRESSED"
            self.level_since = self.clock()
        else:
            self.state = "RAMPING"
            self.resource_health = "HEALTHY"
            if self.admitted_capacity < self.requested_max and self.clock() - self.level_since >= RAMP_HOLD_SECONDS:
                self._step(+1)
        self.last_metrics = curr
        return self.admitted_capacity


# --- QUEUE (scripts/work_queue.py; global options go before the subcommand) ---
def queue_cmd(*args):
    out = subprocess.check_output([sys.executable, QUEUE_SCRIPT, "--state-dir", QUEUE_DIR, "--lease-ttl", "3600", *args])
    return json.loads(out.decode())

def try_claim_task(slot_id):
    try:
        result = queue_cmd("claim", "--worker", slot_id)
        if result.get("claimed"):
            return result["claimed"], ",".join(result.get("scopes", []))
    except Exception:
        pass
    return None, None

def mark_task_complete(task_id, success=True):
    try:
        res = '{"status": "PASS"}' if success else '{"status": "FAIL"}'
        queue_cmd("complete", task_id, "--result-json", res, "--stage", "VERIFYING")
    except Exception:
        pass

def block_task(task_id, reason):
    try:
        queue_cmd("block", task_id, "--reason", reason)
    except Exception:
        pass


# --- SLOT FILES ---
def slot_dir(slot_id):
    d = os.path.join(CLAIMS_DIR, slot_id)
    os.makedirs(d, exist_ok=True)
    return d

def exit_code_path(slot_id):
    return os.path.join(slot_dir(slot_id), "exit_code")

def read_exit_code(slot_id):
    try:
        with open(exit_code_path(slot_id)) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None  # killed without the wrapper finishing

def read_worker_checkpoint(slot_id):
    try:
        with open(os.path.join(slot_dir(slot_id), "checkpoint.json")) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# --- LAUNCHERS ---
def wrap_command(slot_id, cmd):
    """Run cmd, then record its exit code for the supervisor."""
    ec = shlex.quote(exit_code_path(slot_id))
    return f"rm -f {ec}; ( {cmd} ); echo $? > {ec}"

def get_slot_command(slot_id, task_id):
    cfg = load_capacity_config()
    template = cfg.get("slot_command")
    if template:
        values = {"{slot_id}": shlex.quote(slot_id), "{task_id}": shlex.quote(task_id),
                  "{checkpoint}": shlex.quote(os.path.join(slot_dir(slot_id), "checkpoint.json"))}
        for key, value in values.items():
            template = template.replace(key, value)
        return template
    cmd = "muse --yolo" if slot_id.startswith("MUSE") else "HOME=/Users/user/.gemini_alt agy"
    return f"export COURIER_SLOT_ID={shlex.quote(slot_id)} COURIER_TASK_ID={shlex.quote(task_id)}; {cmd}"

def start_screen_session(slot_id, cmd):
    subprocess.run(["screen", "-dmS", slot_id, "bash", "-c", cmd])
    time.sleep(1)
    pid = screen_session_pid(slot_id)
    tty = None
    if pid:
        try: ps_out = subprocess.check_output(["ps", "-ax", "-o", "pid,ppid,tty"]).decode()
        except Exception: ps_out = ""
        for line in ps_out.split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 3 and parts[1] == pid:
                tty = parts[2]
                break
    return pid, tty

def screen_session_pid(slot_id):
    try: out = subprocess.check_output(["screen", "-ls"]).decode()
    except subprocess.CalledProcessError as e: out = e.output.decode() if e.output else ""
    except OSError: return None
    for line in out.split('\n'):
        name = line.strip().split('\t')[0].strip()
        if name.endswith(f".{slot_id}"):
            return name.split('.')[0]
    return None


class ScreenLauncher:
    """Detached screen sessions named after the slot."""
    def start(self, slot_id, cmd):
        return start_screen_session(slot_id, wrap_command(slot_id, cmd))

    def is_alive(self, slot_id, pid):
        return bool(screen_session_pid(slot_id))

    def existing(self, slot_id):
        return screen_session_pid(slot_id)

    def terminate(self, slot_id, pid):
        subprocess.run(["screen", "-S", slot_id, "-X", "quit"], capture_output=True)


# --- STATE (state.tsv is the checkpoint) ---
def load_state():
    if not os.path.exists(STATE_FILE): return []
    with open(STATE_FILE, "r") as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    for row in rows:
        for k in FIELDS:
            if row.get(k) is None: row[k] = ""
    return rows

def save_state(rows):
    if not rows: return
    extra = [k for k in rows[0].keys() if k not in FIELDS]
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS + extra, delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, STATE_FILE)

def _int(v):
    try: return int(v)
    except (TypeError, ValueError): return 0

def _float(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

def verify_proof(proof_ref):
    return os.path.exists(proof_ref) if proof_ref else False


class Supervisor:
    def __init__(self, launcher=None, governor=None, clock=time.time):
        self.launcher = launcher or ScreenLauncher()
        self.clock = clock
        self.gov = governor or CapacityGovernor(requested_max=get_requested_max(load_capacity_config()), clock=clock)

    def _on_exit(self, row, now):
        slot_id = row["slot_id"]
        code = read_exit_code(slot_id)
        runtime = now - _float(row["last_started_at"])
        ckpt = read_worker_checkpoint(slot_id)
        for key in ("branch", "last_commit", "next_task"):
            if ckpt.get(key): row[key] = str(ckpt[key])
        if ckpt.get("proof_ref"): row["proof_ref"] = str(ckpt["proof_ref"])
        row["last_exit_code"] = "" if code is None else str(code)
        row["last_finished_at"] = now_iso(now)
        row["pid"], row["pty"] = "", ""
        row["restart_count"] = str(_int(row["restart_count"]) + 1)

        if row["task_id"] and verify_proof(row["proof_ref"]):
            mark_task_complete(row["task_id"], success=True)
            row["task_id"], row["scope"], row["proof_ref"], row["task_restarts"] = "", "", "", "0"
            row["next_action"] = "start_next_task"
        else:
            row["task_restarts"] = str(_int(row["task_restarts"]) + 1)
            row["next_action"] = "resume_task"
            if row["task_id"] and _int(row["task_restarts"]) >= TASK_RESTART_LIMIT:
                block_task(row["task_id"], "slot_restart_limit_without_proof")
                row["blocker"] = f"task {row['task_id']} blocked after {TASK_RESTART_LIMIT} restarts without proof"
                row["task_id"], row["scope"], row["task_restarts"] = "", "", "0"
                row["next_action"] = "start_next_task"

        if code == RATE_LIMIT_EXIT:
            row["state"], row["backoff_until"] = RATE_LIMITED, str(now + RATE_LIMIT_BACKOFF)
        elif code != 0 and runtime < MIN_HEALTHY_RUNTIME:
            crashes = _int(row["crash_count"]) + 1
            row["crash_count"] = str(crashes)
            if crashes >= CRASH_LIMIT:
                row["state"], row["backoff_until"] = PAUSED_ERROR, ""
                row["blocker"] = f"{crashes} fast exits in a row (last exit {row['last_exit_code'] or 'unknown'})"
            else:
                delay = min(CRASH_BACKOFF_BASE * (2 ** (crashes - 1)), CRASH_BACKOFF_MAX)
                row["state"], row["backoff_until"] = BACKOFF, str(now + delay)
        else:
            row["crash_count"] = "0"
            row["state"], row["backoff_until"] = BACKOFF, str(now + RESTART_BACKOFF)
        row["updated_at"] = now_iso(now)

    def _start(self, row, now):
        slot_id = row["slot_id"]
        existing = self.launcher.existing(slot_id)
        if existing:
            # A session for this slot already exists (e.g. after a supervisor
            # restart): adopt it instead of spawning a duplicate.
            row["state"], row["pid"] = WORKING, str(existing)
            row["updated_at"] = now_iso(now)
            return True
        if not row["task_id"]:
            task_id, scope = try_claim_task(slot_id)
            if not task_id:
                row["state"], row["next_action"] = WAITING, "wait_for_queue"
                return False
            row["task_id"], row["scope"], row["task_restarts"] = task_id, scope, "0"
            row["claim_created_at"] = now_iso(now)
        pid, tty = self.launcher.start(slot_id, get_slot_command(slot_id, row["task_id"]))
        if not pid:
            crashes = _int(row["crash_count"]) + 1
            row["crash_count"], row["blocker"] = str(crashes), "launch_failed"
            if crashes >= CRASH_LIMIT:
                row["state"], row["backoff_until"] = PAUSED_ERROR, ""
            else:
                row["state"], row["backoff_until"] = BACKOFF, str(now + CRASH_BACKOFF_BASE)
            return False
        row["pid"], row["pty"], row["state"] = str(pid), tty or "", WORKING
        row["last_started_at"], row["backoff_until"], row["blocker"] = str(now), "", ""
        row["updated_at"] = now_iso(now)
        with open(os.path.join(slot_dir(slot_id), "owner.txt"), "w") as f:
            f.write(f"session:{slot_id}\npid:{pid}\ntask:{row['task_id']}\nscope:{row['scope']}\n")
        return True

    def tick(self, metrics="read"):
        now = self.clock()
        rows = load_state()
        stopping = os.path.exists(STOP_FILE)
        admitted = self.gov.evaluate(metrics)

        for row in rows:
            if row["state"] == WORKING and not self.launcher.is_alive(row["slot_id"], row["pid"]):
                self._on_exit(row, now)
                if stopping:
                    row["state"], row["backoff_until"] = STOPPED, ""

        active = sum(1 for r in rows if r["state"] == WORKING)
        if not stopping:
            for row in rows:
                if row["state"] not in RUNNABLE:
                    continue
                if _float(row["backoff_until"]) > now:
                    continue
                if active >= admitted or self.gov.state == "BACKOFF":
                    row["state"] = RESOURCE_BLOCKED
                    continue
                if self._start(row, now):
                    active += 1
        save_state(rows)
        return rows


def acquire_lock():
    os.makedirs(WALL_DIR, exist_ok=True)
    fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh

def supervise_loop(run_once=False, canary_mode=False, supervisor=None):
    lock = acquire_lock()
    if lock is None:
        print("Another wall supervisor holds the lock; not starting a second one.")
        return 1
    sup = supervisor or Supervisor(launcher=CanaryLauncher() if canary_mode else None)
    print("Starting Central Supervisor Loop (with Adaptive Governor & Central Queue)...")
    while True:
        rows = sup.tick()
        active = sum(1 for r in rows if r["state"] == WORKING)
        print(f"[GOVERNOR] Active: {active} | Admitted: {sup.gov.admitted_capacity} | State: {sup.gov.state}")
        if run_once or (os.path.exists(STOP_FILE) and active == 0): break
        time.sleep(5)
    return 0


class CanaryLauncher:
    """Legacy canary mode: records a start without launching anything."""
    def start(self, slot_id, cmd): return "CANARY_PID", "CANARY_TTY"
    def is_alive(self, slot_id, pid): return True
    def existing(self, slot_id): return None
    def terminate(self, slot_id, pid): pass


# --- CONTROLLER ---
def cmd_start(target, allow_64=False, loop=True):
    if target not in ALLOWED_TARGETS and not (allow_64 and target == 64):
        print(f"start supports {', '.join(map(str, ALLOWED_TARGETS))} (64 needs --allow-64)")
        return 2
    rows = load_state()
    if not rows:
        print(f"No slots in {STATE_FILE}; run generate_wall_state.py first.")
        return 2
    cfg = load_capacity_config()
    cfg.update({"profile": "CUSTOM", "custom_max": target})
    os.makedirs(WALL_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    if os.path.exists(STOP_FILE): os.remove(STOP_FILE)
    ordered = sorted(rows, key=lambda r: (not r["slot_id"].startswith("MUSE"), r["slot_id"]))
    enabled = {r["slot_id"] for r in ordered[:target]}
    for row in rows:
        if row["slot_id"] in enabled:
            if row["state"] == STOPPED: row["state"] = IDLE
        elif row["state"] != WORKING:
            row["state"] = STOPPED
    save_state(rows)
    print(f"Enabled {len(enabled)} slots (ramp 1-4-8-16-32, resource-gated).")
    return supervise_loop() if loop else 0

def cmd_stop(terminate=False, launcher=None):
    os.makedirs(WALL_DIR, exist_ok=True)
    with open(STOP_FILE, "w") as f: f.write(now_iso())
    rows = load_state()
    launcher = launcher or ScreenLauncher()
    for row in rows:
        if row["state"] == WORKING:
            if terminate: launcher.terminate(row["slot_id"], row["pid"])
        else:
            row["state"] = STOPPED
    save_state(rows)
    print("STOP set: no new starts or restarts." + (" Own screen sessions asked to quit." if terminate else " Running slots finish on their own."))
    return 0

def cmd_resume(slot_id):
    rows = load_state()
    for row in rows:
        if row["slot_id"] == slot_id and row["state"] == PAUSED_ERROR:
            row["state"], row["crash_count"], row["blocker"] = IDLE, "0", ""
            save_state(rows)
            print(f"{slot_id} resumed.")
            return 0
    print(f"{slot_id} is not PAUSED_ERROR.")
    return 1

def cmd_status():
    rows = [r for r in load_state() if r["state"] != STOPPED]
    stop = " STOP set." if os.path.exists(STOP_FILE) else ""
    cfg = load_capacity_config()
    print(f"target={get_requested_max(cfg)} profile={cfg.get('profile')}{stop}")
    print("slot\tstate\ttask\tbranch\tlast_commit\texit\trestarts\tcrashes\tnext")
    for r in rows:
        print("\t".join([r["slot_id"], r["state"], r["task_id"] or "-", r["branch"] or "-", (r["last_commit"] or "-")[:10],
                         r["last_exit_code"] or "-", r["restart_count"] or "0", r["crash_count"] or "0", r["next_task"] or r["next_action"] or "-"]))
    return 0

def show_dashboard():
    print("\033[2J\033[H=== COURIER CUSTOMER WORKER CAPACITY DASHBOARD ===")
    rows = load_state()
    if not rows: return
    stats = {s: 0 for s in (WORKING, "VERIFYING", WAITING, "BLOCKED", "DONE", IDLE, "RESULT_READY", BACKOFF, PAUSED_ERROR, STOPPED, RESOURCE_BLOCKED, RATE_LIMITED)}
    for i, row in enumerate(rows):
        state = row['state']
        if state in stats: stats[state] += 1
        col = "\033[92m" if state==WORKING else "\033[91m" if state in ("BLOCKED", PAUSED_ERROR) else "\033[90m" if state in [IDLE, WAITING, STOPPED] else "\033[93m"
        print(f"{col}{row['slot_id']}:{state[:3]:<4}\033[0m", end="")
        if (i + 1) % 8 == 0: print()
    cfg = load_capacity_config()
    print("\n\n=== CUSTOMER CAPACITY METRICS ===")
    print(f"PROFILE:          {cfg.get('profile', 'AUTO')} (Max requested: {get_requested_max(cfg)})")
    print("---")
    print(" | ".join(f"{k}: {v}" for k, v in stats.items() if v))
    print("=====================================================")

def set_profile(profile, custom_max=4):
    cfg = load_capacity_config()
    cfg.update({"profile": profile, "custom_max": custom_max})
    os.makedirs(WALL_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Capacity profile updated to: {profile} (Max: {custom_max})")

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv: print(__doc__); return 1
    cmd = argv[0]
    if cmd == "start" and len(argv) > 1:
        return cmd_start(int(argv[1]), allow_64="--allow-64" in argv, loop="--no-loop" not in argv)
    if cmd == "status": return cmd_status()
    if cmd == "stop": return cmd_stop(terminate="--terminate" in argv)
    if cmd == "resume" and len(argv) > 1: return cmd_resume(argv[1])
    if cmd == "dashboard": return show_dashboard()
    if cmd == "attach": os.execvp("screen", ["screen", "-r", argv[1]])
    if cmd == "supervise": return supervise_loop(run_once=("--once" in argv))
    if cmd == "canary": return supervise_loop(run_once=("--once" in argv), canary_mode=True)
    if cmd == "profile": return set_profile(argv[1], int(argv[2]) if len(argv) > 2 else 4)
    print(__doc__)
    return 1

if __name__ == "__main__": sys.exit(main() or 0)
