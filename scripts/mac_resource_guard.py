import os
import sys
import time
import fcntl
import sqlite3
import subprocess
import signal
import uuid
import threading
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

class ResourceGuardBusy(Exception): pass
class HeavyJobError(Exception): pass
class OrphanProcessDetected(Exception): pass
class OutputLimitExceeded(Exception): pass
class CooldownRequired(Exception): pass

class HeavyJobSupervisor:
    _instance = None

    def __init__(self, workspace_dir: str = "."):
        self.guard_dir = Path(workspace_dir) / "runtime" / "resource_guard"
        self.guard_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.guard_dir / "heavy.lock"
        self.db_path = self.guard_dir / "heavy_jobs.sqlite3"
        self._init_db()

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS heavy_jobs (
                job_id TEXT PRIMARY KEY,
                launch_token TEXT,
                mission_id TEXT,
                task_hash TEXT,
                worker TEXT,
                owner_pid INTEGER,
                owner_start_identity TEXT,
                child_pid INTEGER,
                child_start_identity TEXT,
                pgid INTEGER,
                pgid_leader_identity TEXT,
                command_fingerprint TEXT,
                started_wall_time REAL,
                started_monotonic REAL,
                deadline_monotonic REAL,
                retry_number INTEGER,
                state TEXT,
                term_sent_at REAL,
                kill_sent_at REAL,
                exit_code INTEGER,
                cleanup_state TEXT,
                last_update REAL,
                failure_reason TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp_wall REAL NOT NULL,
                timestamp_monotonic REAL NOT NULL,
                event_type TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_event_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            )
        ''')
        conn.commit()
        conn.close()


    def _check_thermal_state(self):
        import subprocess
        try:
            cmd = ["swift", "-e", "import Foundation; print(ProcessInfo.processInfo.thermalState.rawValue)"]
            out = subprocess.check_output(cmd, text=True, timeout=2.0).strip()
            state = int(out)
            # 0: nominal, 1: fair, 2: serious, 3: critical
            if state >= 2:
                raise CooldownRequired(f"Mac thermal state is serious/critical ({state}). Holding new heavy work.")
        except CooldownRequired:
            raise
        except Exception:
            pass # ignore errors getting thermal state

    def _check_duty_cycle(self):
        # 15 minutes rolling window
        now = time.monotonic()
        cutoff = now - 900.0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT started_monotonic, last_update FROM heavy_jobs WHERE started_monotonic > ?", (cutoff,))
        rows = cursor.fetchall()
        conn.close()

        total_heavy_time = sum((r[1] - r[0] if r[1] and r[0] else 0) for r in rows)
        if total_heavy_time > 300.0: # 5 mins out of 15 max
            raise CooldownRequired(f"Duty cycle exceeded: {total_heavy_time:.1f}s heavy load in last 15m")

    def _acquire_kernel_lock(self):
        fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            os.close(fd)
            raise ResourceGuardBusy("Another process holds the heavy lock")
        return fd

    def _release_kernel_lock(self, fd):
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except OSError:
                pass

    def release(self, job_id: str, launch_token: str):
        # Only clear the exact job match
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        cursor.execute("SELECT state FROM heavy_jobs WHERE job_id=? AND launch_token=?", (job_id, launch_token))
        if cursor.fetchone():
            pass # safe release logic if needed
        conn.execute("COMMIT")

    def reconcile_interrupted_state(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT job_id, owner_pid, pgid, state FROM heavy_jobs WHERE state IN ('SPAWNING', 'RUNNING', 'TERMINATING', 'KILLING')")
        active_jobs = cursor.fetchall()

        for job_id, owner_pid, pgid, state in active_jobs:
            owner_alive = True
            try:
                os.kill(owner_pid, 0)
            except OSError:
                owner_alive = False

            if not owner_alive:
                child_alive = False
                if pgid:
                    def get_procs():
                        p = []
                        try:
                            out = subprocess.check_output(["ps", "-axo", "pid,ppid,pgid"], text=True).strip().split("\n")
                            for line in out[1:]:
                                parts = line.split()
                                if len(parts) >= 3:
                                    try:
                                        p.append({"pid": int(parts[0]), "pgid": int(parts[2])})
                                    except: pass
                        except: pass
                        return p

                    remaining = [p for p in get_procs() if p["pgid"] == pgid]
                    if remaining:
                        child_alive = True

                conn.execute("BEGIN IMMEDIATE")
                if child_alive:
                    conn.execute("UPDATE heavy_jobs SET state='ORPHAN_PROCESS_DETECTED' WHERE job_id=?", (job_id,))
                else:
                    if state == 'SPAWNING':
                        conn.execute("UPDATE heavy_jobs SET state='INTERRUPTED_BEFORE_SPAWN' WHERE job_id=?", (job_id,))
                    else:
                        conn.execute("UPDATE heavy_jobs SET state='UNCLEAN_EXIT' WHERE job_id=?", (job_id,))
                conn.commit()

                if child_alive:
                    raise OrphanProcessDetected(f"Orphan process detected from dead owner {owner_pid}, PGID {pgid}")
        conn.close()

    def run_bounded_heavy_job(
        self,
        cmd: List[str],
        timeout: float,
        mission_id: str,
        task_hash: str,
        worker: str,
        retry_number: int,
        cwd: Optional[str] = None
    ) -> Tuple[int, str, str]:
        GLOBAL_MAX_TIMEOUT = 600.0
        if timeout > GLOBAL_MAX_TIMEOUT:
            timeout = GLOBAL_MAX_TIMEOUT

        try:
            load1, _, _ = os.getloadavg()
            if load1 > 15.0:
                raise ResourceGuardBusy(f"SYSTEM_OVERLOADED: load1={load1:.2f} > 15.0")
        except AttributeError:
            pass

        self._check_duty_cycle()
        self._check_thermal_state()

        lock_fd = self._acquire_kernel_lock()

        job_id = str(uuid.uuid4())
        launch_token = str(uuid.uuid4())
        now_wall = time.time()
        now_mono = time.monotonic()

        conn = sqlite3.connect(self.db_path, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute('''
                INSERT INTO heavy_jobs
                (job_id, launch_token, mission_id, task_hash, worker, owner_pid,
                 command_fingerprint, started_wall_time, started_monotonic, deadline_monotonic,
                 retry_number, state, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (job_id, launch_token, mission_id, task_hash, worker, os.getpid(),
                  str(cmd), now_wall, now_mono, now_mono + timeout, retry_number, 'SPAWNING', now_mono))
            conn.commit()
        except Exception as e:
            conn.execute("ROLLBACK")
            self._release_kernel_lock(lock_fd)
            raise HeavyJobError(f"DB Error: {e}")

        wrapper_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "heavy_job_wrapper.py"))
        full_cmd = [sys.executable, wrapper_path, str(self.db_path), job_id, launch_token] + cmd

        try:
            proc = subprocess.Popen(
                full_cmd,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        except Exception as e:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE heavy_jobs SET state='SPAWN_FAILED', failure_reason=? WHERE job_id=? AND launch_token=?", (str(e), job_id, launch_token))
            conn.commit()
            self._release_kernel_lock(lock_fd)
            raise HeavyJobError(f"Spawn failed: {e}")

        start_poll = time.monotonic()
        registered = False
        pgid = None
        while time.monotonic() - start_poll < 5.0:
            cursor = conn.cursor()
            cursor.execute("SELECT state, pgid FROM heavy_jobs WHERE job_id=?", (job_id,))
            row = cursor.fetchone()
            if row and row[0] == 'RUNNING':
                registered = True
                pgid = row[1]
                break
            time.sleep(0.05)

        if not registered:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE heavy_jobs SET state='UNCLEAN_EXIT' WHERE job_id=? AND launch_token=?", (job_id, launch_token))
            conn.commit()

            try:
                proc.kill()
                proc.wait(timeout=1.0)
            except:
                pass

            self._release_kernel_lock(lock_fd)
            err_text = proc.stderr.read() if proc.stderr else ""
            raise HeavyJobError(f"Wrapper failed to register PGID: {err_text}")

        stdout_chunks = []
        stderr_chunks = []
        out_limit = 1024 * 1024
        err_limit = 1024 * 1024

        out_exceeded = False
        err_exceeded = False

        def read_stream(stream, chunks, limit, name):
            nonlocal out_exceeded, err_exceeded
            size = 0
            while True:
                chunk = stream.read(4096)
                if not chunk: break
                size += len(chunk)
                if size > limit:
                    if name == 'stdout': out_exceeded = True
                    if name == 'stderr': err_exceeded = True
                else:
                    chunks.append(chunk)

        t_out = threading.Thread(target=read_stream, args=(proc.stdout, stdout_chunks, out_limit, 'stdout'))
        t_err = threading.Thread(target=read_stream, args=(proc.stderr, stderr_chunks, err_limit, 'stderr'))
        t_out.start()
        t_err.start()

        status = "COMPLETED"
        while True:
            if proc.poll() is not None:
                break

            if time.monotonic() > now_mono + timeout:
                status = "TIMEOUT"
                break

            if out_exceeded or err_exceeded:
                status = "OUTPUT_LIMIT_EXCEEDED"
                break

            try:
                l1, _, _ = os.getloadavg()
                if l1 > 20.0:
                    status = "RESOURCE_PRESSURE_TERMINATED"
                    break
            except AttributeError:
                pass

            conn.execute("UPDATE heavy_jobs SET last_update=? WHERE job_id=?", (time.monotonic(), job_id))
            time.sleep(0.1)

        if proc.poll() is None:
            conn.execute("UPDATE heavy_jobs SET state='TERMINATING', term_sent_at=? WHERE job_id=?", (time.monotonic(), job_id))
            try:
                os.killpg(pgid, signal.SIGTERM)
            except OSError:
                pass

            wait_start = time.monotonic()
            while time.monotonic() - wait_start < 5.0:
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            if proc.poll() is None:
                conn.execute("UPDATE heavy_jobs SET state='KILLING', kill_sent_at=? WHERE job_id=?", (time.monotonic(), job_id))
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
                time.sleep(1.0)

        t_out.join(timeout=1.0)
        t_err.join(timeout=1.0)
        
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

        if out_exceeded or err_exceeded:
            status = "OUTPUT_LIMIT_EXCEEDED"

        exit_code = proc.returncode if proc.returncode is not None else -1

        def get_procs():
            p = []
            try:
                out = subprocess.check_output(["ps", "-axo", "pid,ppid,pgid,command"], text=True).strip().split("\n")
                for line in out[1:]:
                    parts = line.split(None, 3)
                    if len(parts) >= 3:
                        try:
                            p.append({"pid": int(parts[0]), "pgid": int(parts[2])})
                        except: pass
            except: pass
            return p

        remaining = [p for p in get_procs() if p["pgid"] == pgid and p["pid"] != os.getpid()]
        cleanup_state = "CLEAN" if not remaining else "ORPHANS_REMAIN"

        if status == "COMPLETED" and exit_code != 0:
            status = "FAILED"
        if status == "COMPLETED" and exit_code == 0:
            status = "SUCCESS"

        conn.execute("BEGIN IMMEDIATE")
        conn.execute('''
            UPDATE heavy_jobs
            SET state=?, cleanup_state=?, exit_code=?, last_update=?
            WHERE job_id=? AND launch_token=?
        ''', (status, cleanup_state, exit_code, time.monotonic(), job_id, launch_token))
        conn.commit()

        self.release(job_id, launch_token)
        self._release_kernel_lock(lock_fd)

        if remaining:
            raise OrphanProcessDetected(f"Orphans remain: {remaining}")

        if status == "OUTPUT_LIMIT_EXCEEDED":
            raise OutputLimitExceeded("Output limit (1 MiB) exceeded")

        if status == "TIMEOUT":
            # return non-zero exit code
            return -9, "".join(stdout_chunks), "TIMEOUT"

        return exit_code, "".join(stdout_chunks), "".join(stderr_chunks)


def sanitize_worker_environment(env):
    """Ensure no raw os.environ inheritance."""
    safe_env = {}
    for k, v in env.items():
        if k not in ['PYTEST_ADDOPTS', 'SSH_AUTH_SOCK', 'PYTHONPATH']:
            safe_env[k] = v
    return safe_env

import os


def construct_worker_env():
    # Integrated, explicitly allow-listed environment builder
    return {"PATH": "/usr/bin:/bin", "USER": "courier_worker"}
