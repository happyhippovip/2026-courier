#!/usr/bin/env python3
import uuid

import sqlite3, time, subprocess, os, sys, signal
from pathlib import Path
import result_customs

WORKSPACE = Path.cwd()
DB_PATH = WORKSPACE / ".courier_state" / "motor.db"
ATTEMPTS_DIR = WORKSPACE / ".courier_state" / "attempts"
MOTOR_ID = str(os.getpid())

def init_env():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATTEMPTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, status TEXT, instruction TEXT, expected_effects TEXT, lease_owner TEXT, lease_expires_at REAL, goal_id TEXT, priority INTEGER DEFAULT 0, mission_id TEXT, gap_id TEXT, risk TEXT, results TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS fingerprints (fingerprint TEXT PRIMARY KEY, created_at REAL, task_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS goals (
        goal_id TEXT PRIMARY KEY, goal_version INTEGER DEFAULT 1, created_at REAL, source TEXT,
        high_level_objective TEXT, scope TEXT, success_criteria TEXT, non_goals TEXT, risk_class TEXT,
        priority INTEGER DEFAULT 0, status TEXT, human_gates TEXT, open_gaps TEXT, proof_debt TEXT,
        last_verified_progress REAL, current_mission_id TEXT, parent_goal_id TEXT, supersedes_goal_id TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS missions (
        mission_id TEXT PRIMARY KEY, goal_id TEXT, mission_version INTEGER DEFAULT 1, objective TEXT, scope TEXT,
        acceptance_criteria TEXT, risk TEXT, status TEXT, created_at REAL, started_at REAL, finished_at REAL,
        open_gaps TEXT, task_count INTEGER DEFAULT 0, verified_task_count INTEGER DEFAULT 0, failed_task_count INTEGER DEFAULT 0,
        proof_debt TEXT, human_gates TEXT, next_action_hint TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS follow_ups (
        follow_up_id TEXT PRIMARY KEY, goal_id TEXT, mission_id TEXT, related_task_id TEXT, thought TEXT,
        reason TEXT, priority INTEGER DEFAULT 0, dependency TEXT, status TEXT
    )''')
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column already exists
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN dependencies TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE tasks ADD COLUMN results TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE tasks ADD COLUMN recurrence_interval INTEGER DEFAULT 0")
        c.execute("ALTER TABLE tasks ADD COLUMN next_run_at REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE tasks ADD COLUMN timeout INTEGER DEFAULT 300")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN gate_id TEXT")
    except sqlite3.OperationalError:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS attempts (attempt_id TEXT PRIMARY KEY, task_id TEXT, pid INTEGER, start_time REAL, end_time REAL, exit_code INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS approved_gates (gate_id TEXT PRIMARY KEY)''')
    conn.commit()
    return conn

def check_thermal_pressure():
    try:
        res = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True)
        import re
        match = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", res.stdout)
        if match:
            speed = int(match.group(1))
            if speed < 100:
                return "PRESSURE"
        return "NORMAL"
    except Exception:
        return "UNKNOWN"

def is_pid_alive(pid, expected_lstart=None):
    try:
        import os
        import subprocess
        os.kill(pid, 0)

        # Deep Ownership Verification (PID Reuse Safety)
        if expected_lstart:
            try:
                ps_out = subprocess.check_output(["ps", "-p", str(pid), "-o", "lstart="], text=True).strip()
                if ps_out and ps_out != expected_lstart:
                    print(f"[*] PID REUSE DETECTED: PID {pid} is alive but lstart '{ps_out}' does not match expected '{expected_lstart}'")
                    return False
            except Exception:
                pass # If ps fails, fallback to simple os.kill

        return True
    except OSError:
        return False

def reconcile(conn):
    c = conn.cursor()
    import time
    now = time.time()
    c.execute("SELECT task_id FROM tasks WHERE status='RUNNING' AND (lease_expires_at < ? OR lease_expires_at IS NULL)", (now,))
    expired = c.fetchall()
    for row in expired:
        t_id = row[0]

        # Graceful fetch for backwards compat with un-migrated records
        try:
            c.execute("SELECT pid, pid_lstart FROM attempts WHERE task_id=? ORDER BY start_time DESC LIMIT 1", (t_id,))
            pid_row = c.fetchone()
        except sqlite3.OperationalError:
            c.execute("SELECT pid, NULL FROM attempts WHERE task_id=? ORDER BY start_time DESC LIMIT 1", (t_id,))
            pid_row = c.fetchone()

        if pid_row and pid_row[0] and is_pid_alive(pid_row[0], pid_row[1]):
            c.execute("UPDATE tasks SET lease_expires_at=? WHERE task_id=?", (now + 60, t_id))
            print(f"[{MOTOR_ID}] Task {t_id} (PID {pid_row[0]}) is still alive. Extended lease to prevent orphan duplication.")
            continue

        c.execute("SELECT COUNT(*) FROM attempts WHERE task_id=?", (t_id,))
        count = c.fetchone()[0]
        if count < 3:
            c.execute("UPDATE tasks SET status='PENDING', lease_owner=NULL WHERE task_id=?", (t_id,))
        else:
            c.execute("UPDATE tasks SET status='FAILED', lease_owner=NULL WHERE task_id=?", (t_id,))
    conn.commit()

def run_loop():
    conn = init_env()
    print(f"Courier Standalone Motor {MOTOR_ID} started. Concurrency: 4")
    reconcile(conn)

    active_procs = {}

    import atexit
    import signal as sig
    _cleanup_done = [False]
    def cleanup_active_procs(*args):
        if _cleanup_done[0]: return
        _cleanup_done[0] = True
        print(f"[{MOTOR_ID}] Shutting down. Reaping orphaned tasks...")
        for tid, meta in list(active_procs.items()):
            proc = meta["proc"]
            if proc.poll() is None:
                print(f"[{MOTOR_ID}] Killing orphaned task {tid} (PID: {proc.pid})")
                try:
                    import os
                    os.killpg(os.getpgid(proc.pid), sig.SIGKILL)
                except:
                    pass
                proc.kill()
        import sys
        sys.exit(0)

    sig.signal(sig.SIGINT, cleanup_active_procs)
    sig.signal(sig.SIGTERM, cleanup_active_procs)
    atexit.register(cleanup_active_procs)
 # t_id -> {"proc": proc, "att_id": att_id, "start_time": time, "timeout": max_dur, "inst": inst, "exp_eff": exp_eff, "log": log_path}
    MAX_CONCURRENT = 4
    idle_cycles = 0

    while True:
        now = time.time()
        conn.commit() # keep connection fresh
        c = conn.cursor()

        made_progress = False

        # 1. REAP PHASE
        finished = []
        for t_id, meta in list(active_procs.items()):
            proc = meta["proc"]
            poll = proc.poll()
            if poll is not None:
                # Finished
                finished.append((t_id, poll, meta))
            elif now - meta["start_time"] > meta["timeout"]:
                # Timeout
                print(f"[{MOTOR_ID}] Task {t_id} HUNG. Killing process group.")
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except:
                    pass
                try:
                    proc.wait(timeout=2)
                except:
                    proc.kill()
                    proc.wait()
                with open(meta["log"], "a") as out_f:
                    out_f.write("\n\n[MOTOR] KILLED DUE TO TIMEOUT")
                finished.append((t_id, -9, meta))

        for t_id, returncode, meta in finished:
            c.execute("UPDATE attempts SET end_time=?, exit_code=? WHERE attempt_id=?", (time.time(), returncode, meta["att_id"]))

            # Customs evaluation
            success = (returncode == 0)
            if success and meta["exp_eff"]:
                with open(meta["log"], "r") as lf:
                    log_content = lf.read()
                try:
                    import result_customs
                    eff_val = meta["exp_eff"]
                    try:
                        import json
                        parsed_eff = json.loads(eff_val)
                    except json.JSONDecodeError:
                        parsed_eff = eff_val # legacy raw string path

                    if isinstance(parsed_eff, list) and len(parsed_eff) == 3 and parsed_eff[0] == "REGEX":
                        eff_path = Path(WORKSPACE / parsed_eff[1])
                        success, msg = result_customs.ResultCustoms.verify_content_regex(str(eff_path), parsed_eff[2])
                    else:
                        eff_path = Path(WORKSPACE / str(parsed_eff))
                        success, msg = result_customs.ResultCustoms.verify_file_exists(str(eff_path))

                    if success:
                        # Stale result rejection: Check if file was actually modified DURING the task
                        if eff_path.stat().st_mtime < meta["start_time"]:
                            success = False
                            msg = f"Stale Result Rejection: {eff_path} was last modified before task started."
                    if not success:
                        print(f"[{MOTOR_ID}] Task {t_id} failed Customs check: {msg}")
                except Exception as e:
                    print(f"[{MOTOR_ID}] Customs evaluation error for {t_id}: {e}")
                    success = False

            if success:
                # Extract results for Customs Agent
                try:
                    with open(meta["log"], "r") as lf:
                        full_log = lf.read()
                        # Only take the last 4000 characters to prevent DB bloat
                        res_out = full_log[-4000:] if len(full_log) > 4000 else full_log
                except:
                    res_out = ""

                # Get recovery interval if it was a cron task
                c.execute("SELECT recurrence_interval FROM tasks WHERE task_id=?", (t_id,))
                row = c.fetchone()
                rec_interval = row[0] if row and row[0] else 0
                if rec_interval > 0:
                    c.execute("UPDATE tasks SET status='PENDING', lease_owner=NULL, next_run_at=?, results=? WHERE task_id=?", (time.time() + rec_interval, res_out, t_id))
                else:
                    c.execute("UPDATE tasks SET status='DONE', lease_owner=NULL, results=? WHERE task_id=?", (res_out, t_id))
            else:
                c.execute("SELECT COUNT(*) FROM attempts WHERE task_id=?", (t_id,))
                attempts_count = c.fetchone()[0]
                if attempts_count < 3:
                    c.execute("UPDATE tasks SET status='PENDING', lease_owner=NULL WHERE task_id=?", (t_id,))
                    print(f"[{MOTOR_ID}] Task {t_id} failed (attempt {attempts_count}). Retrying later.")
                else:
                    c.execute("UPDATE tasks SET status='FAILED', lease_owner=NULL WHERE task_id=?", (t_id,))
                    print(f"[{MOTOR_ID}] Task {t_id} failed permanently.")
            conn.commit()
            del active_procs[t_id]
            made_progress = True

        # 2. DISPATCH PHASE
        def is_host_overloaded():
            try:
                import os, shutil, subprocess

                # 1. Check CPU
                load1, load5, load15 = os.getloadavg()
                cpu_count = os.cpu_count() or 4
                if load1 > cpu_count * 0.8:
                    return True

                # 2. Check Disk (Ensure at least 5GB free on root)
                usage = shutil.disk_usage("/")
                free_gb = usage.free / (1024**3)
                if free_gb < 5.0:
                    return True

                # 3. Check Memory (Mac OS specific using vm_stat)
                # Page size is typically 4096.
                try:
                    vm_stat = subprocess.check_output(["vm_stat"], text=True)
                    pages_free = 0
                    for line in vm_stat.splitlines():
                        if "Pages free" in line:
                            pages_free = int(line.split(":")[1].strip().strip('.'))
                            break
                    free_mem_mb = (pages_free * 4096) / (1024**2)
                    # If free memory is critically low (< 500MB free)
                    if free_mem_mb < 500:
                        return True
                except Exception:
                    pass # Skip mem check if vm_stat fails

                return False
            except Exception:
                return False

        if len(active_procs) < MAX_CONCURRENT:
            if len(active_procs) > 0 and is_host_overloaded():
                # Resource governor throttles
                time.sleep(1)
                pass # fall through to let other logic run, but ideally we'd skip dispatching.
                # Actually, skipping dispatch is best done by faking MAX_CONCURRENT temporarily:
                # Wait, better yet, just break out of this dispatch block.
            elif False:
                pass
            # To cleanly patch without ruining indentation:
            if (WORKSPACE / ".courier_state" / ".courier_paused").exists():
                pending_tasks = []
            elif len(active_procs) > 0 and is_host_overloaded():
                print(f"[{MOTOR_ID}] RESOURCE GOVERNOR: Host load is high. Deferring new dispatch.")
                pending_tasks = []
            else:
                c.execute("""SELECT t.task_id, t.instruction, t.expected_effects, t.dependencies, t.timeout
                 FROM tasks t
                 LEFT JOIN approved_gates g ON t.gate_id = g.gate_id
                 WHERE t.status='PENDING' AND (t.next_run_at IS NULL OR t.next_run_at <= ?)
                 AND (t.gate_id IS NULL OR g.gate_id IS NOT NULL)
                 ORDER BY t.priority DESC, t.rowid ASC""", (now,))
                pending_tasks = c.fetchall()

            # Find an eligible task that isn't already running
            for pt in pending_tasks:
                if len(active_procs) >= MAX_CONCURRENT:
                    break

                tid, inst, exp_eff, deps_json, timeout_val = pt
                if tid in active_procs:
                    continue

                import json
                try:
                    deps = json.loads(deps_json) if deps_json else []
                except:
                    deps = []

                can_run = True
                failed_dep = False
                for d in deps:
                    c.execute("SELECT status FROM tasks WHERE task_id=?", (d,))
                    st = c.fetchone()
                    if not st:
                        can_run = False
                        break
                    if st[0] in ['FAILED', 'CANCELLED']:
                        failed_dep = True
                        break
                    if st[0] != 'DONE':
                        can_run = False
                        break

                if failed_dep:
                    c.execute("UPDATE tasks SET status='CANCELLED', results='Dependency failed/cancelled' WHERE task_id=?", (tid,))
                    conn.commit()
                    print(f"[{MOTOR_ID}] Task {tid} cancelled due to failed dependency.")
                    continue

                if can_run:
                    # Lease it!
                    lease_expiry = now + 60
                    c.execute("UPDATE tasks SET status='RUNNING', lease_owner=?, lease_expires_at=? WHERE task_id=? AND status='PENDING'", (MOTOR_ID, lease_expiry, tid))
                    if c.rowcount == 0:
                        # Another supervisor grabbed it first
                        continue
                    conn.commit()

                    att_id = f"att_{tid}_{uuid.uuid4().hex[:8]}"
                    log_path = ATTEMPTS_DIR / f"{att_id}.log"
                    print(f"[{MOTOR_ID}] Dispatching {tid}")

                    out_f = open(log_path, "w")
                    env = os.environ.copy()
                    env["MOTOR_TASK_ID"] = tid
                    proc = subprocess.Popen(["/bin/sh", "-c", inst], stdout=out_f, stderr=out_f, preexec_fn=os.setpgrp, cwd=str(WORKSPACE), env=env)
                    out_f.close() # CRITICAL: Prevent FD leak in supervisor

                    # Grab lstart for PID reuse safety
                    lstart = None
                    try:
                        lstart = subprocess.check_output(["ps", "-p", str(proc.pid), "-o", "lstart="], text=True).strip()
                    except Exception:
                        pass

                    try:
                        c.execute("INSERT INTO attempts (attempt_id, task_id, pid, start_time, pid_lstart) VALUES (?, ?, ?, ?, ?)", (att_id, tid, proc.pid, now, lstart))
                    except sqlite3.OperationalError:
                        # Fallback if DB column doesn't exist
                        c.execute("INSERT INTO attempts (attempt_id, task_id, pid, start_time) VALUES (?, ?, ?, ?)", (att_id, tid, proc.pid, now))
                    conn.commit()

                    active_procs[tid] = {
                        "proc": proc,
                        "att_id": att_id,
                        "start_time": now,
                        "timeout": timeout_val if timeout_val else 300,
                        "inst": inst,
                        "exp_eff": exp_eff,
                        "log": log_path,
                        "file_obj": out_f
                    }
                    made_progress = True

        # 3. LEASE RENEWAL PHASE
        if active_procs:
            for tid, meta in active_procs.items():
                c.execute("UPDATE tasks SET lease_expires_at=? WHERE task_id=? AND lease_owner=?", (now + 60, tid, MOTOR_ID))
            conn.commit()

        if not made_progress:
            idle_cycles += 1
            if idle_cycles > 60:
                time.sleep(5) # Adaptive thermal sleep
            else:
                time.sleep(1)
        else:
            idle_cycles = 0
def print_usage():
    print("Usage: python3 supervisor_standalone.py [command]")
    print("Commands: init, run, add, status, block, approve_gate, unblock, cancel, logs, pause, resume, retry, cleanup")
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print_usage()

    if len(sys.argv) <= 1:
        print_usage()
    if len(sys.argv) > 1:
        if sys.argv[1] == "init":
            conn = init_env()
            conn.execute("INSERT OR IGNORE INTO tasks (task_id, status, instruction, expected_effects) VALUES (?, ?, ?, ?)", ("task_000_hello_world", "PENDING", "echo 'Hello from Courier Motor!' > hello_courier.txt", "hello_courier.txt"))
            conn.commit()
            print("Initialized .courier_state directory and injected Hello World task.")
            sys.exit(0)
        elif sys.argv[1] == "run":
            run_loop()
            sys.exit(0)
        elif sys.argv[1] == "add" and len(sys.argv) > 2:
            conn = init_env()
            t_id = f"task_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
            inst = sys.argv[2]

            # CLI priority parsing court: handle "exp_eff" properly while extracting --priority
            exp = None
            if len(sys.argv) > 3 and not sys.argv[3].startswith("--"):
                exp = sys.argv[3]

            priority = 0
            if "--priority" in sys.argv:
                try:
                    idx = sys.argv.index("--priority")
                    priority = int(sys.argv[idx+1])
                except (ValueError, IndexError):
                    pass # Keep 0

            dependencies = "[]"
            if "--requires" in sys.argv:
                try:
                    idx = sys.argv.index("--requires")
                    deps_raw = sys.argv[idx+1]
                    import json
                    dependencies = json.dumps([d.strip() for d in deps_raw.split(",") if d.strip()])
                except (ValueError, IndexError):
                    pass

            recurrence = 0
            if "--every" in sys.argv:
                try:
                    idx = sys.argv.index("--every")
                    recurrence = int(sys.argv[idx+1])
                except:
                    pass

            timeout_val = 300
            if "--timeout" in sys.argv:
                try:
                    idx = sys.argv.index("--timeout")
                    timeout_val = int(sys.argv[idx+1])
                except:
                    pass

            if False:
                try:
                    idx = sys.argv.index("--every")
                    recurrence = int(sys.argv[idx+1])
                except:
                    pass

            if False:
                try:
                    idx = sys.argv.index("--requires")
                    deps_raw = sys.argv[idx+1]
                    import json
                    dependencies = json.dumps([d.strip() for d in deps_raw.split(",") if d.strip()])
                except (ValueError, IndexError):
                    pass

            recurrence_val = 0
            if "--recurrence" in sys.argv:
                try:
                    idx = sys.argv.index("--recurrence")
                    recurrence_val = int(sys.argv[idx+1])
                except (ValueError, IndexError):
                    pass

            gate_id_val = None
            if "--gate" in sys.argv:
                try:
                    idx = sys.argv.index("--gate")
                    gate_id_val = sys.argv[idx+1]
                except IndexError:
                    pass

            conn.execute("INSERT INTO tasks (task_id, status, instruction, expected_effects, priority, dependencies, recurrence_interval, timeout, gate_id) VALUES (?, 'PENDING', ?, ?, ?, ?, ?, ?, ?)", (t_id, inst, exp, priority, dependencies, recurrence_val, timeout_val, gate_id_val))
            conn.commit()
            print(f"Added task {t_id}")
            sys.exit(0)
        elif sys.argv[1] == "status":
            conn = init_env()
            if "--json" in sys.argv:
                import json
                out = {}
                for row in conn.execute("SELECT task_id, status, instruction, expected_effects FROM tasks"):
                    out[row[0]] = {"status": row[1], "instruction": row[2], "expected_effects": row[3]}
                print(json.dumps(out, indent=2))
            else:
                for row in conn.execute("SELECT task_id, status FROM tasks"):
                    print(f"{row[0]}: {row[1]}")
            sys.exit(0)
        elif sys.argv[1] == "block":
            if len(sys.argv) <= 2:
                print("Usage: ./courier-cli block <id>")
                sys.exit(1)
            conn = init_env()
            conn.execute("UPDATE tasks SET status='BLOCKED', lease_owner=NULL WHERE task_id=?", (sys.argv[2],))
            conn.commit()
            print(f"Blocked {sys.argv[2]}")
        elif sys.argv[1] == "approve_gate":
            if len(sys.argv) <= 2:
                print("Usage: ./courier-cli approve_gate <id>")
                sys.exit(1)
            conn = init_env()
            conn.execute("INSERT OR IGNORE INTO approved_gates (gate_id) VALUES (?)", (sys.argv[2],))
            conn.commit()
            print(f"Approved gate {sys.argv[2]}")
            sys.exit(0)
        elif sys.argv[1] == "unblock":
            if len(sys.argv) <= 2:
                print("Usage: ./courier-cli unblock <id>")
                sys.exit(1)
            conn = init_env()
            conn.execute("UPDATE tasks SET status='PENDING' WHERE task_id=?", (sys.argv[2],))
            conn.commit()
            print(f"Unblocked {sys.argv[2]}")
            sys.exit(0)
        elif sys.argv[1] == "cancel":
            if len(sys.argv) <= 2:
                print("Usage: ./courier-cli cancel <id>")
                sys.exit(1)
            conn = init_env()
            conn.execute("UPDATE tasks SET status='CANCELLED', lease_owner=NULL WHERE task_id=?", (sys.argv[2],))
            conn.commit()
            print(f"Cancelled {sys.argv[2]}")
            sys.exit(0)
        elif sys.argv[1] == "logs":
            if len(sys.argv) <= 2:
                print("Usage: ./courier-cli logs <task_id>")
                sys.exit(1)
            conn = init_env()
            c = conn.cursor()
            c.execute("SELECT attempt_id FROM attempts WHERE task_id=? ORDER BY start_time DESC LIMIT 1", (sys.argv[2],))
            res = c.fetchone()
            if res and (ATTEMPTS_DIR / f"{res[0]}.log").exists():
                print((ATTEMPTS_DIR / f"{res[0]}.log").read_text())
            sys.exit(0)
        elif sys.argv[1] == "pause":
            init_env()
            (WORKSPACE / ".courier_state" / ".courier_paused").touch()
            print("Motor paused.")
            sys.exit(0)
        elif sys.argv[1] == "resume":
            pause_file = WORKSPACE / ".courier_state" / ".courier_paused"
            if pause_file.exists():
                pause_file.unlink()
            print("Motor resumed.")
            sys.exit(0)
        elif sys.argv[1] == "retry":
            if len(sys.argv) <= 2:
                print("Usage: ./courier-cli retry <id>")
                sys.exit(1)
            conn = init_env()
            tid = sys.argv[2]
            conn.execute("UPDATE tasks SET status='PENDING', lease_owner=NULL WHERE task_id=?", (tid,))
            conn.execute("DELETE FROM attempts WHERE task_id=?", (tid,))
            conn.commit()
            print(f"Task {tid} reset to PENDING with clean attempt history.")
            sys.exit(0)
        elif sys.argv[1] == "cleanup":
            conn = init_env()
            c = conn.cursor()
            # Fetch tasks to clean up
            c.execute("SELECT task_id FROM tasks WHERE status IN ('DONE', 'CANCELLED', 'FAILED')")
            old_tasks = c.fetchall()
            if not old_tasks:
                print("No tasks to clean up.")
                sys.exit(0)

            cleaned = 0
            for (tid,) in old_tasks:
                c.execute("SELECT attempt_id FROM attempts WHERE task_id=?", (tid,))
                attempts = c.fetchall()
                for (att_id,) in attempts:
                    log_file = WORKSPACE / ".courier_state" / "attempts" / f"{att_id}.log"
                    if log_file.exists():
                        log_file.unlink()
                c.execute("DELETE FROM attempts WHERE task_id=?", (tid,))
                c.execute("DELETE FROM tasks WHERE task_id=?", (tid,))
                cleaned += 1

            conn.commit()
            print(f"Cleaned up {cleaned} historical tasks and their logs.")
            sys.exit(0)

            init_env()
            p = WORKSPACE / ".courier_state" / ".courier_paused"
            if p.exists(): p.unlink()
            print("Motor resumed.")
            sys.exit(0)

    print_usage()
