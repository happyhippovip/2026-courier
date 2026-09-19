import subprocess
import ctypes
from ctypes import wintypes
import time
import os
import threading
import uuid
import sqlite3
from pathlib import Path

# Windows API Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9

class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]

class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]

_BG_JOBS = {}

def get_db_path():
    state_dir = Path(__file__).parent / 'state'
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / 'queue.db'

class BoundedRunner:
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        self._start_orphan_reaper()
        
    def _start_orphan_reaper(self):
        def reaper_loop():
            import tempfile, psutil
            while True:
                try:
                    time.sleep(300) # Every 5 minutes
                    
                    # 1. Reap stuck Courier processes by querying DB
                    db_path = get_db_path()
                    with sqlite3.connect(db_path) as c:
                        c.row_factory = sqlite3.Row
                        # Find jobs running longer than 1 hour (3600s)
                        cursor = c.execute("SELECT job_id, pid, create_time FROM background_jobs WHERE status = 'RUNNING' AND (julianday('now') - julianday(started_at)) * 24 * 60 * 60 > 3600")
                        for row in cursor.fetchall():
                            try:
                                proc = psutil.Process(row['pid'])
                                # Verify it's exactly the same process by comparing create_time
                                # Allow a small float tolerance (1.0s) because psutil create_time might slightly differ from our Python time.time()
                                if abs(proc.create_time() - row['create_time']) < 5.0:
                                    print(f"Reaping owned Courier job: PID {proc.pid}")
                                    for child in proc.children(recursive=True):
                                        child.kill()
                                    proc.kill()
                            except Exception:
                                pass
                        
                        # 2. Cleanup stale DB background_jobs
                        c.execute("UPDATE background_jobs SET status = 'TIMEOUT', exit_code = -1 WHERE status = 'RUNNING' AND (julianday('now') - julianday(started_at)) * 24 * 60 > 60")
                        
                    # 3. Cleanup stale temp files
                    temp_dir = Path(tempfile.gettempdir())
                    now = time.time()
                    for ext in ('*.out', '*.err'):
                        for f in temp_dir.glob('tmp' + ext):
                            if f.is_file() and now - f.stat().st_mtime > 86400:
                                try: f.unlink()
                                except Exception: pass
                except Exception:
                    pass
                    
        t = threading.Thread(target=reaper_loop, daemon=True)
        t.start()
        
    def _create_job_object(self):
        job = self.kernel32.CreateJobObjectW(None, None)
        if not job:
            raise RuntimeError(f"CreateJobObjectW failed: {self.kernel32.GetLastError()}")
            
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        
        result = self.kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(limits),
            ctypes.sizeof(limits)
        )
        if not result:
            self.kernel32.CloseHandle(job)
            raise RuntimeError(f"SetInformationJobObject failed: {self.kernel32.GetLastError()}")
            
        return job
        
    def run(self, cmd, timeout=30, background=False, task_id=None, attempt_id=None, execution_id=None):
        start_time = time.time()
        status = 'FAILED'
        stderr_msg = ''
        stdout_msg = ''
        
        import tempfile
        out_fd, out_path = tempfile.mkstemp(suffix='.out')
        err_fd, err_path = tempfile.mkstemp(suffix='.err')
        
        job = self._create_job_object()
        job_id = str(uuid.uuid4())
        
        try:
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000008
            process = subprocess.Popen(
                cmd,
                stdout=out_fd,
                stderr=err_fd,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=flags
            )
            
            # Immediately assign to job object
            try:
                handle = int(process._handle)
                success = self.kernel32.AssignProcessToJobObject(job, handle)
                if not success:
                    print(f"[Runner] Warning: AssignProcessToJobObject failed: {self.kernel32.GetLastError()}")
            except Exception as e:
                print(f"[Runner] Error assigning process to job: {e}")

            if background:
                _BG_JOBS[job_id] = job
                
                try:
                    p_info = psutil.Process(process.pid)
                    create_time = p_info.create_time()
                    executable = p_info.exe()
                except Exception:
                    create_time = time.time()
                    executable = cmd[0] if cmd else "unknown"

                db_path = get_db_path()
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        "INSERT INTO background_jobs (job_id, task_id, attempt_id, execution_id, pid, create_time, executable, status, stdout_path, stderr_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (job_id, task_id, attempt_id, execution_id, process.pid, create_time, executable, 'RUNNING', out_path, err_path)
                    )
                
                def background_supervisor(p, j_id, j_handle, out_p, err_p, out_f, err_f, hard_timeout):
                    try:
                        p.wait(timeout=hard_timeout)
                        exit_code = p.returncode
                        bg_status = 'SUCCESS' if exit_code == 0 else 'FAILED'
                    except subprocess.TimeoutExpired:
                        exit_code = -1
                        bg_status = 'TIMEOUT'
                    except Exception as e:
                        exit_code = -1
                        bg_status = 'FAILED'
                    finally:
                        try: p.kill()
                        except Exception: pass
                        try: self.kernel32.CloseHandle(j_handle)
                        except Exception: pass
                        if j_id in _BG_JOBS:
                            del _BG_JOBS[j_id]
                        try: os.close(out_f)
                        except Exception: pass
                        try: os.close(err_f)
                        except Exception: pass
                        
                    with sqlite3.connect(get_db_path()) as c:
                        c.execute(
                            "UPDATE background_jobs SET status = ?, exit_code = ?, completed_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                            (bg_status, exit_code, j_id)
                        )

                t = threading.Thread(target=background_supervisor, args=(process, job_id, job, out_path, err_path, out_fd, err_fd, timeout), daemon=True)
                t.start()
                
                return {
                    'status': 'SUCCESS',
                    'stdout': f'Task detached to background job {job_id}',
                    'stderr': '',
                    'run_id': str(process.pid),
                    'job_id': job_id,
                    'command_category': 'native_powershell',
                    'start_timestamp': start_time,
                    'hard_timeout': timeout,
                    'exit_code': 0,
                }

            try:
                process.wait(timeout=timeout)
                status = 'SUCCESS' if process.returncode == 0 else 'FAILED'
            except subprocess.TimeoutExpired:
                status = 'TIMEOUT'
                stderr_msg = f'[TIMEOUT/HANG] Fast Triage: task exceeded {timeout}s timeout'
            except Exception as e:
                status = 'FAILED'
                stderr_msg = str(e)
            
        finally:
            if not background:
                if 'process' in locals():
                    try: process.kill()
                    except Exception: pass
                    
                self.kernel32.CloseHandle(job)
                
                if 'process' in locals():
                    try: process.wait(timeout=1.0)
                    except Exception: pass
                
                try: os.close(out_fd)
                except Exception: pass
                try: os.close(err_fd)
                except Exception: pass

        if not background:
            def read_bounded(path, limit=2_000_000):
                try:
                    size = os.path.getsize(path)
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        if size > limit:
                            f.seek(size - limit)
                            return "[TRUNCATED...]\n" + f.read()
                        return f.read()
                except Exception as e:
                    return f"[Error reading log: {e}]"
                finally:
                    try: os.remove(path)
                    except: pass

            stdout_msg = read_bounded(out_path).strip()
            final_stderr = read_bounded(err_path)
            if stderr_msg:
                final_stderr = stderr_msg + '\n' + final_stderr
                
            return {
                'status': status,
                'stdout': stdout_msg,
                'stderr': final_stderr,
                'run_id': str(process.pid) if 'process' in locals() else 'unknown',
                'job_id': job_id,
                'command_category': 'native_powershell',
                'start_timestamp': start_time,
                'hard_timeout': timeout,
                'exit_code': process.returncode if 'process' in locals() and hasattr(process, 'returncode') else -1,
            }

runner = BoundedRunner()

def run_command_bounded(cmd, timeout=30, background=False, task_id=None, attempt_id=None, execution_id=None):
    return runner.run(cmd, timeout=timeout, background=background, task_id=task_id, attempt_id=attempt_id, execution_id=execution_id)
