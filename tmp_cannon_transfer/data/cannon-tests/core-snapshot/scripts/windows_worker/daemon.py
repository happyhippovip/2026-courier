import json, time, os, sys, shutil, subprocess
from pathlib import Path
import urllib.request
import urllib.error
import tempfile
import uuid
import hashlib
import threading
import ctypes
import winreg
import sqlite3

def load_config():
    config_path = Path(__file__).parent / 'config.json'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

_cfg = load_config()
API_URL = os.environ.get('COURIER_SERVER') or _cfg.get('COURIER_SERVER') or 'http://127.0.0.1:8080'

from scripts.redaction import get_secret, apply_redaction

API_KEY = get_secret("api_key")

if not API_KEY:
    print('[Windows Worker] FATAL: No COURIER_API_KEY found in environment or OS keyring.', flush=True)
    sys.exit(1)

apply_redaction([API_KEY])

print(f'[Windows Worker] Using API_KEY prefix: {API_KEY[:4]}...', flush=True)
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

def register_worker(worker_id):
    req = urllib.request.Request(f'{API_URL}/workers/register', method='POST')
    for k, v in HEADERS.items(): req.add_header(k, v)
    cost_class = os.environ.get('WORKER_COST_CLASS', 'low')
    data = json.dumps({'worker_id': worker_id, 'platform': 'windows', 'capabilities': ['windows', 'platform_neutral'], 'cost_class': cost_class}).encode('utf-8')
    try:
        urllib.request.urlopen(req, data=data, timeout=10)
        print(f'[{worker_id}] Registered successfully')
        return True
    except Exception as e:
        print(f'[{worker_id}] Failed to register: {e}')
        return False

def http_post_result(res):
    req = urllib.request.Request(f'{API_URL}/tasks/result', method='POST')
    for k, v in HEADERS.items(): req.add_header(k, v)
    data = json.dumps(res).encode('utf-8')
    for attempt in range(5):
        try:
            urllib.request.urlopen(req, data=data, timeout=10)
            return
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            print(f'[Windows Worker] Failed to post result: {e} - {err_msg}')
            if e.code == 400:
                raise ValueError(f"Fatal 400: {err_msg}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f'[Windows Worker] Failed to post result: {e}')
            time.sleep(2 ** attempt)
    raise RuntimeError('Failed to post result after 5 attempts')

def get_db_path():
    state_dir = Path(__file__).parent / 'state'
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / 'queue.db'

def init_db():
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS inbox (
                task_id TEXT PRIMARY KEY,
                task_json TEXT NOT NULL,
                status TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS outbox (
                task_id TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                status TEXT NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS background_jobs (
                job_id TEXT PRIMARY KEY,
                task_id TEXT,
                attempt_id TEXT,
                execution_id TEXT,
                pid INTEGER,
                create_time REAL,
                executable TEXT,
                status TEXT NOT NULL,
                exit_code INTEGER,
                stdout_path TEXT,
                stderr_path TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

def run_native(task, config):
    print(f"[{config.get('WORKER_ID', 'default-win-worker')}] Running native task {task['task_id']}...")
    instruction = task.get('instruction', '')
    out_clean = ''
    stderr = ''
    run_id = 'win-native'

    print(f"[{config.get('WORKER_ID', 'default-win-worker')}] Executing native PowerShell instruction.")
    
    try:
        from . import shell_helpers
    except ImportError:
        import shell_helpers
        
    original_instruction = instruction
    instruction = shell_helpers.preprocess_instruction(instruction)
    if instruction != original_instruction:
        print(f"[{config.get('WORKER_ID', 'default-win-worker')}] Translated instruction for native platform: {instruction}")

    cmd = ['powershell', '-Command', instruction]
    
    try:
        from . import runner
    except ImportError:
        import runner
        
    background = task.get('background', False)
    timeout = task.get('timeout', 30)
        
    res = runner.run_command_bounded(
        cmd, 
        timeout=timeout, 
        background=background, 
        task_id=task.get('task_id'),
        attempt_id=task.get('attempt_id'),
        execution_id=task.get('execution_ref')
    )
    
    status = res['status']
    out_clean = res['stdout']
    stderr = res['stderr']
    run_id = res['run_id']
    
    # Fast Bug Triage Layer
    if "CommandNotFoundException" in out_clean or "CommandNotFoundException" in stderr:
        status = 'FAILED'
        stderr = "[ENVIRONMENT/SHELL ISSUE] Fast Triage: CommandNotFoundException detected. This is a shell/environment capability failure, not a code bug.\n" + stderr
            
    artifacts = []
    if status == 'SUCCESS':
        expected = task.get('artifacts', [])
        workspace = Path(os.getcwd())
        for relative_name in expected:
            artifact_path = workspace / relative_name
            if artifact_path.is_file():
                artifacts.append({
                    'path': relative_name,
                    'sha256': hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                })
            else:
                status = 'FAILED'
                stderr += f'\nMissing artifact: {relative_name}'

    res_json = {
        'status': status,
        'stdout': out_clean,
        'stderr': stderr,
        'goal_id': task.get('goal_id'),
        'task_id': task.get('task_id'),
        'attempt_id': task.get('attempt_id'),
        'dispatch_id': task.get('dispatch_id'),
        'execution_ref': task.get('execution_ref'),
        'worker_id': task.get('worker_id') or config.get('WORKER_ID', 'default-win-worker'),
        'provider': 'windows_native',
        'run_id': run_id,
        'result_id': f'result-{uuid.uuid4().hex}',
        'artifacts': artifacts if status == 'SUCCESS' else []
    }
    if 'batch_id' in task: res_json['batch_id'] = task['batch_id']
    if 'prompt_id' in task: res_json['prompt_id'] = task['prompt_id']
    return res_json

def run_agy(task, config):
    print(f"[{config.get('WORKER_ID', 'default-win-worker')}] Running AI task {task['task_id']} via agy...")
    instruction = task.get('instruction', task.get('description', ''))
    
    prompt = f"Task ID: {task['task_id']}\nInstruction: {instruction}\n\nYou are a headless worker on Windows. You MUST execute the instruction. After you have successfully executed the instruction, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did. IMPORTANT: Your current working directory is {os.getcwd()}. Any file artifacts you create MUST be relative to this directory."
    
    agy_bin = shutil.which("agy")
    if not agy_bin:
        agy_bin = "agy"
            
    cmd = [agy_bin, "-p", prompt, "--dangerously-skip-permissions"]
    
    try:
        from . import runner
    except ImportError:
        import runner
        
    timeout = task.get('timeout', 300)
    background = task.get('background', False)
    
    res = runner.run_command_bounded(
        cmd, 
        timeout=timeout, 
        background=background, 
        task_id=task.get('task_id'),
        attempt_id=task.get('attempt_id'),
        execution_id=task.get('execution_ref')
    )
    
    status = res['status']
    out_clean = res['stdout']
    stderr = res['stderr']
    run_id = res['run_id']

    if "CommandNotFoundException" in out_clean or "CommandNotFoundException" in stderr:
        status = 'FAILED'
        stderr = "[ENVIRONMENT/SHELL ISSUE] Fast Triage: CommandNotFoundException detected. This is a shell/environment capability failure, not a code bug.\n" + stderr
    
    if out_clean and len(out_clean) > 50000:
        out_clean = "...[TRUNCATED]..." + out_clean[-50000:]
    if stderr and len(stderr) > 20000:
        stderr = "...[TRUNCATED]..." + stderr[-20000:]
        
    parsed = False
    res_json_ext = {}
    if "```json" in out_clean:
        try:
            ext = out_clean.split("```json")[1].split("```")[0].strip()
            res_json_ext = json.loads(ext)
            parsed = True
        except:
            pass

    combined_out = (out_clean + " " + stderr).lower()
    if any(kw in combined_out for kw in ["429", "too many requests", "quota", "rate limit", "resource exhausted", "provider unavailable"]):
        status = "PROVIDER_WAIT"

    if status == 'SUCCESS' and not parsed:
        status = 'FAILED'
        stderr += '\nFailed to parse final JSON output from agy.'

    artifacts = []
    if status == 'SUCCESS':
        expected = task.get('artifacts', [])
        workspace = Path(os.getcwd())
        for relative_name in expected:
            artifact_path = workspace / relative_name
            if artifact_path.is_file():
                artifacts.append({
                    'path': relative_name,
                    'sha256': hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                })
            else:
                status = 'FAILED'
                stderr += f'\nMissing artifact: {relative_name}'

    res_json = {
        'status': status,
        'stdout': out_clean,
        'stderr': stderr,
        'goal_id': task.get('goal_id'),
        'task_id': task.get('task_id'),
        'attempt_id': task.get('attempt_id'),
        'dispatch_id': task.get('dispatch_id'),
        'execution_ref': task.get('execution_ref'),
        'worker_id': task.get('worker_id') or config.get('WORKER_ID', 'default-win-worker'),
        'provider': 'windows_antigravity',
        'run_id': run_id,
        'result_id': f'result-{uuid.uuid4().hex}',
        'artifacts': artifacts if status == 'SUCCESS' else []
    }
    if status == "PROVIDER_WAIT":
        res_json["reason"] = "QUOTA_OR_RATE_LIMIT"
        
    if 'batch_id' in task: res_json['batch_id'] = task['batch_id']
    if 'prompt_id' in task: res_json['prompt_id'] = task['prompt_id']
    return res_json

def run_task(task, config):
    mode = task.get("mode", "ANTIGRAVITY")
    
    # Heuristic for backwards compat: if it says 'echo', it's native
    if "mac" in task.get("target_agent", "").lower() and mode == "ANTIGRAVITY" and "echo" in task.get("instruction", "").lower():
        mode = "NATIVE"
    
    # Handle workspace
    workspace = task.get("workspace")
    if workspace:
        try:
            os.chdir(workspace)
        except FileNotFoundError:
            res_json = {
                'status': 'FAILED',
                'stdout': '',
                'stderr': f"Workspace {workspace} not found. Out of scope.",
                'goal_id': task.get('goal_id'),
                'task_id': task.get('task_id'),
                'attempt_id': task.get('attempt_id'),
                'dispatch_id': task.get('dispatch_id'),
                'execution_ref': task.get('execution_ref'),
                'worker_id': task.get('worker_id') or config.get('WORKER_ID', 'default-win-worker'),
                'provider': 'windows_validation',
                'run_id': 'validation-fail',
                'result_id': f'result-{uuid.uuid4().hex}',
                'artifacts': []
            }
            return res_json

    if mode == "NATIVE":
        return run_native(task, config)
    else:
        return run_agy(task, config)

import psutil

def is_resource_pressure_high(config=None):
    if config is None:
        config = load_config()
    profile = os.environ.get('WORKER_PROFILE', config.get('WORKER_PROFILE', 'LOW_RESOURCE'))
    
    cpu_threshold = 100.0
    mem_threshold = 100.0
    if profile == 'STANDARD':
        cpu_threshold = 95.0
        mem_threshold = 95.0
    elif profile == 'HIGH_CAPACITY':
        cpu_threshold = 98.0
        mem_threshold = 98.0
        
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu = 0.0
        mem = 0.0
        
    sim_cpu = float(os.environ.get('SIMULATE_CPU_PERCENT', -1))
    sim_mem = float(os.environ.get('SIMULATE_MEM_PERCENT', -1))
    
    if sim_cpu >= 0: cpu = sim_cpu
    if sim_mem >= 0: mem = sim_mem
    
    return cpu > cpu_threshold or mem > mem_threshold

_mutex_handle = None

def acquire_lock(worker_id):
    global _mutex_handle
    mutex_name = f'Global\\CourierWorker_{worker_id}'
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)
        return False
    _mutex_handle = mutex
    return True

def setup_autostart(worker_id):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
        python_exe = sys.executable
        script_path = os.path.abspath(__file__)
        cmd = f'"{python_exe}" "{script_path}"'
        winreg.SetValueEx(key, f'CourierWorker_{worker_id}', 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
    except Exception as e:
        print(f'[{worker_id}] Failed to set registry autostart: {e}')

def heartbeat_loop(worker_id):
    while True:
        try:
            req = urllib.request.Request(f'{API_URL}/workers/heartbeat', method='POST')
            for k, v in HEADERS.items(): req.add_header(k, v)
            data = json.dumps({'worker_id': worker_id}).encode('utf-8')
            try:
                urllib.request.urlopen(req, data=data, timeout=10)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    register_worker(worker_id)
        except Exception:
            pass
        time.sleep(30)

def fetcher_loop(worker_id):
    error_backoff = 10
    while True:
        try:
            req = urllib.request.Request(f'{API_URL}/tasks/claim', method='POST')
            for k, v in HEADERS.items(): req.add_header(k, v)
            data = json.dumps({'worker_id': worker_id}).encode('utf-8')
            res = urllib.request.urlopen(req, data=data, timeout=35)
            res_data = json.loads(res.read().decode('utf-8'))
            task = res_data.get('task')
            if task:
                task_id = task['task_id']
                attempt_id = task.get('attempt_id')
                with sqlite3.connect(get_db_path()) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT result_json FROM outbox WHERE task_id = ?", (task_id,))
                    existing = cursor.fetchone()
                    re_queue = False
                    if existing:
                        try:
                            res_json = json.loads(existing[0])
                            if res_json.get('attempt_id') == attempt_id:
                                re_queue = True
                        except:
                            pass
                    
                    if re_queue:
                        conn.execute("UPDATE outbox SET status = 'PENDING' WHERE task_id = ?", (task_id,))
                        print(f'[{worker_id}] Task {task_id} attempt {attempt_id} already in outbox. Re-queueing result for send.')
                    else:
                        conn.execute("DELETE FROM outbox WHERE task_id = ?", (task_id,))
                        conn.execute("INSERT OR REPLACE INTO inbox (task_id, task_json, status) VALUES (?, ?, ?)", (task_id, json.dumps(task), 'QUEUED'))
                        print(f'[{worker_id}] Task {task_id} attempt {attempt_id} queued in inbox.')
            else:
                time.sleep(2.0)
            error_backoff = 10
        except Exception as e:
            print(f'[{worker_id}] Fetcher error: {e}')
            time.sleep(error_backoff)
            error_backoff = min(300, error_backoff * 2)
            continue

def sender_loop(worker_id):
    while True:
        try:
            with sqlite3.connect(get_db_path()) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT task_id, result_json FROM outbox WHERE status = 'PENDING' ORDER BY completed_at ASC")
                rows = cursor.fetchall()
            for row in rows:
                task_id = row['task_id']
                result = json.loads(row['result_json'])
                try:
                    http_post_result(result)
                    with sqlite3.connect(get_db_path()) as conn:
                        conn.execute("UPDATE outbox SET status = 'SENT' WHERE task_id = ?", (task_id,))
                    print(f'[{worker_id}] Task {task_id} result sent.')
                except ValueError as e:
                    print(f'[{worker_id}] Fatal error sending result for {task_id}: {e}. Dropping from outbox.')
                    with sqlite3.connect(get_db_path()) as conn:
                        conn.execute("DELETE FROM outbox WHERE task_id = ?", (task_id,))
                except Exception as e:
                    print(f'[{worker_id}] Sender failed to post result for {task_id}: {e}')
                    break 
        except Exception as e:
            print(f'[{worker_id}] Sender error: {e}')
        time.sleep(0.5)

def cleanup_loop(worker_id):
    while True:
        try:
            with sqlite3.connect(get_db_path()) as conn:
                conn.execute("DELETE FROM outbox WHERE status = 'SENT' AND completed_at < datetime('now', '-7 days')")
                conn.execute("DELETE FROM inbox WHERE status = 'DONE' AND added_at < datetime('now', '-7 days')")
        except Exception as e:
            print(f'[{worker_id}] Cleanup error: {e}')
        time.sleep(3600)

def loop():
    config = load_config()
    worker_id = os.environ.get('COURIER_WORKER_ID') or config.get('WORKER_ID', 'default-win-worker')
    if not acquire_lock(worker_id):
        print(f'[{worker_id}] Another instance is already running. Exiting to prevent duplicates.')
        sys.exit(0)
    try:
        print(f'[{worker_id}] Windows Worker HTTP Daemon started. PID={os.getpid()}')
        init_db()
        threading.Thread(target=heartbeat_loop, args=(worker_id,), daemon=True).start()
        threading.Thread(target=fetcher_loop, args=(worker_id,), daemon=True).start()
        threading.Thread(target=sender_loop, args=(worker_id,), daemon=True).start()
        threading.Thread(target=cleanup_loop, args=(worker_id,), daemon=True).start()
        
        with sqlite3.connect(get_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT task_id, task_json FROM inbox WHERE status = 'RUNNING'")
            crashed_tasks = cursor.fetchall()
            for row in crashed_tasks:
                task = json.loads(row['task_json'])
                task_id = task.get('task_id')
                print(f'[{worker_id}] Found ambiguous crash marker for task {task_id}')
                
                expected = task.get('artifacts', [])
                workspace = Path(os.getcwd())
                artifacts = []
                artifacts_produced = True
                
                if expected:
                    for relative_name in expected:
                        artifact_path = workspace / relative_name
                        if artifact_path.is_file():
                            artifacts.append({
                                'path': relative_name,
                                'sha256': hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                            })
                        else:
                            artifacts_produced = False
                            break
                else:
                    artifacts_produced = False
                
                if expected and artifacts_produced:
                    status = 'SUCCESS'
                    stderr = 'Recovered after crash (artifacts found). VERIFY_AFTER_CRASH passed.'
                else:
                    status = 'FAILED'
                    stderr = 'AMBIGUOUS_CRASH: Worker crashed during external effect. VERIFY_AFTER_CRASH required.'
                    artifacts = []

                res_json = {
                    'status': status,
                    'stdout': '',
                    'stderr': stderr,
                    'goal_id': task.get('goal_id'),
                    'task_id': task_id,
                    'attempt_id': task.get('attempt_id'),
                    'dispatch_id': task.get('dispatch_id'),
                    'execution_ref': task.get('execution_ref'),
                    'worker_id': worker_id,
                    'provider': 'windows_native',
                    'run_id': 'crashed-unknown',
                    'result_id': f'result-{uuid.uuid4().hex}',
                    'artifacts': artifacts
                }
                if 'batch_id' in task: res_json['batch_id'] = task['batch_id']
                if 'prompt_id' in task: res_json['prompt_id'] = task['prompt_id']
                conn.execute("INSERT OR REPLACE INTO outbox (task_id, result_json, status) VALUES (?, ?, ?)", (task_id, json.dumps(res_json), 'PENDING'))
                conn.execute("UPDATE inbox SET status = 'QUARANTINE' WHERE task_id = ?", (task_id,))
                
        while True:
            try:
                if is_resource_pressure_high(config):
                    time.sleep(5.0)
                    continue
                task = None
                with sqlite3.connect(get_db_path()) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT task_id, task_json FROM inbox WHERE status = 'QUEUED' ORDER BY added_at ASC LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        task = json.loads(row['task_json'])
                        conn.execute("UPDATE inbox SET status = 'RUNNING' WHERE task_id = ?", (task['task_id'],))
                if task:
                    result = run_task(task, config)
                    with sqlite3.connect(get_db_path()) as conn:
                        conn.execute("INSERT OR REPLACE INTO outbox (task_id, result_json, status) VALUES (?, ?, ?)", (task['task_id'], json.dumps(result), 'PENDING'))
                        conn.execute("UPDATE inbox SET status = 'DONE' WHERE task_id = ?", (task['task_id'],))
                    print(f"[{worker_id}] Task {task['task_id']} completed and queued for sending.")
                else:
                    time.sleep(0.5)
            except Exception as e:
                print(f'[{worker_id}] Executor error: {e}')
                time.sleep(5.0)
    finally:
        pass

if __name__ == '__main__':
    loop()
