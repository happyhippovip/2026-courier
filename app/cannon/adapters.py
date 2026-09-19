import importlib.util
import os
import sys
from .processes import launch_gated
from .storage import ROOT, atomic, digest, owned, read


class FakeAdapter:
    """Interface is explicit; only the test adapter may start a process in V1."""
    MODES = {'SUCCESS', 'FAILURE', 'TIMEOUT', 'MALFORMED_RESULT', 'DELAYED_RESULT', 'CANCEL'}

    def __init__(self, contract_path, workspace):
        self.contract_path = str(contract_path)
        self.workspace = owned(workspace); self.workspace.mkdir(parents=True, exist_ok=True)
        spec = importlib.util.spec_from_file_location('cannon_canonical_contract', self.contract_path)
        self.contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.contract)
        self.handles = {}

    def discover(self):
        return {'kind': 'FAKE_PROCESS', 'interface': ['discover', 'health', 'execute', 'result', 'cancel'], 'provider_calls': 0}

    def health(self):
        return {'available': True, 'kind': 'FAKE_PROCESS'}

    def execute(self, task, folder, persist_identity):
        folder = owned(folder); folder.mkdir(parents=True, exist_ok=True)
        mode = task.get('fake_mode', 'SUCCESS')
        delay = task.get('fake_delay', .03)
        if mode not in self.MODES or not isinstance(delay, (int, float)) or not 0 <= delay <= 10:
            raise ValueError('Unsupported bounded fake scenario')
        execution = task['execution_ref']
        if execution in self.handles:
            raise RuntimeError('Execution already owned')
        request = {'task': task, 'mode': mode, 'delay': delay, 'workspace': str(self.workspace),
                   'contract': self.contract_path, 'result': str(folder / 'result.json'), 'events': str(folder / 'event.json')}
        atomic(folder / 'request.json', request)
        env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH'}}
        env['PYTHONPATH'] = str(ROOT / 'app'); env['PYTHONDONTWRITEBYTECODE'] = '1'
        # Bypass the Windows venv redirector; own the actual interpreter.
        command = [getattr(sys, '_base_executable', sys.executable), '-m', 'cannon.fake_worker', str(folder / 'request.json')]
        child, job, identity = launch_gated(command, str(self.workspace), env)
        self.handles[execution] = (child, job)
        identity.update(task_id=task['task_id'], attempt_id=task['attempt_id'], execution_id=execution,
                        dispatch_id=task['dispatch_id'], worker_id=task['worker_id'])
        try:
            # Persist binding before the child can perform any effect.
            atomic(folder / 'process.json', identity)
            persist_identity(identity)
            child.stdin.write(b'GO\n'); child.stdin.flush()
        except BaseException:
            self.close_execution(execution); raise
        return child

    def result(self, task, folder):
        raw = read(owned(folder) / 'result.json')
        if not raw:
            raise ValueError('MISSING_RESULT')
        return self.contract.validate_durable_result(task, raw)

    def cancel(self, execution_id):
        child, _ = self.handles[execution_id]
        if child.poll() is None:
            try:
                child.stdin.write(b'CANCEL\n'); child.stdin.flush()
            except (OSError, ValueError):
                pass

    def close_execution(self, execution_id):
        entry = self.handles.pop(execution_id, None)
        if not entry: return
        child, job = entry
        try:
            if child.poll() is None:
                # Exact owned process handle only; never PID/name lookup.
                child.kill()
            child.wait(timeout=5)
        finally:
            job.close()
            if child.stdin: child.stdin.close()

    def close(self):
        for execution in list(self.handles):
            self.close_execution(execution)



class LiveMuseAdapter:
    """Live integration using muse exec --json."""
    
    def __init__(self, contract_path, workspace):
        self.contract_path = str(contract_path)
        self.workspace = owned(workspace); self.workspace.mkdir(parents=True, exist_ok=True)
        spec = importlib.util.spec_from_file_location('cannon_canonical_contract', self.contract_path)
        self.contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.contract)
        self.handles = {}

    def discover(self):
        return {'kind': 'REAL_MUSE', 'execution': 'UNPROVEN'}

    def health(self):
        import shutil
        return {'available': bool(shutil.which('muse')), 'state': 'UNPROVEN', 'kind': 'REAL_MUSE'}

    @staticmethod
    def validate_canary_terminal(events, path, nonce, sha):
        import json
        terminals = [e.get('payload', {}) for e in events
                     if e.get('payload_type') == 'run.terminal.completed']
        if len(terminals) != 1 or terminals[0].get('terminal') != 'completed':
            raise ValueError('MISSING_OR_AMBIGUOUS_TERMINAL_RESULT')
        result = json.loads(terminals[0].get('text', ''))
        if result != {'path': str(path), 'nonce': nonce, 'sha256': sha}:
            raise ValueError('WRONG_CANARY_RESULT')
        return result

    @staticmethod
    def execute_canary(task, results_dir, persist_identity, timeout=90):
        """Bounded real Meta canary; independent file verification, never exit-only success."""
        import hashlib
        import json
        import shutil
        import subprocess
        import tempfile
        import time
        import uuid
        from pathlib import Path
        if task.get('provider', 'meta') != 'meta':
            raise ValueError('UNSUPPORTED_REAL_PROVIDER')
        if task.get('acceptance') != 'isolated_nonce_canary_v1':
            raise ValueError('UNSUPPORTED_REAL_TASK_CONTRACT')
        executable = shutil.which('muse')
        if not executable:
            raise ValueError('MUSE_EXECUTABLE_MISSING')
        execution = str(uuid.uuid4())
        target = Path('/tmp') / ('courier-live-canary-' + execution + '.txt')
        nonce = uuid.uuid4().hex
        folder = Path(results_dir) / execution
        folder.mkdir(parents=True, exist_ok=False)
        prompt = ('Create ONLY the file ' + str(target) + ' containing exactly ' + nonce +
                  ' with no newline. Do not modify anything else. Return a JSON object with path, nonce, sha256. '
                  'If permissions prevent this, report failure. Do not request permission changes.')
        prompt_file = folder / 'prompt.txt'
        prompt_file.write_text(prompt, encoding='utf-8')
        identity = {'executor_kind': 'REAL_MUSE', 'provider': 'meta', 'task_id': task['task_id'],
                    'execution_id': execution, 'worker_id': 'muse-' + execution,
                    'started_at': time.time(), 'heartbeat_at': time.time(), 'terminal': False}
        command = [executable, 'exec', '--json', '--provider', 'meta', '--reasoning-effort', 'low',
                   '--max-model-steps', '6', '--workspace', str(target.parent),
                   '--prompt-file', str(prompt_file),
                   '--no-foreign-personal-context', '--no-session-log', '--disable-web-tools']
        env = dict(os.environ, MUSE_NO_AUTO_UPDATE='1')
        persist_identity(identity)
        with (folder / 'stdout.jsonl').open('wb') as out, (folder / 'stderr.txt').open('wb') as err:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                     cwd=str(target.parent), env=env, start_new_session=True)
            identity['pid'] = child.pid
            try:
                deadline = time.monotonic() + timeout
                while child.poll() is None:
                    identity['heartbeat_at'] = time.time()
                    persist_identity(dict(identity))
                    if time.monotonic() >= deadline:
                        raise ValueError('MUSE_TIMEOUT_UNKNOWN_EFFECT')
                    time.sleep(.25)
                if child.returncode != 0:
                    raise ValueError('MUSE_NONZERO_EXIT:' + str(child.returncode))
            finally:
                if child.poll() is None:
                    child.terminate()
                    try: child.wait(timeout=3)
                    except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=3)
                identity.update(terminal=True, finished_at=time.time(), exit_code=child.returncode)
                persist_identity(dict(identity))
        raw = (folder / 'stdout.jsonl').read_text(encoding='utf-8')
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if not any(e.get('payload_type') == 'run.terminal.completed' for e in events):
            raise ValueError('MISSING_TERMINAL_RESULT')
        if target.is_symlink() or not target.is_file() or target.read_bytes() != nonce.encode():
            raise ValueError('CANARY_SIDE_EFFECT_NOT_VERIFIED')
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
        # Only the explicit terminal answer counts; prompt/log echoes never count.
        LiveMuseAdapter.validate_canary_terminal(events, target, nonce, sha)
        result_id = execution + ':r1'
        receipt = dict(identity, result_id=result_id, outcome='ok', path=str(target), nonce=nonce, sha256=sha)
        path = Path(results_dir) / (task['task_id'] + '.result.json')
        temporary = path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            json.dump(receipt, stream); stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
        return 'ok', result_id

    def execute(self, task, folder, persist_identity):
        raise ValueError('LEGACY_EXIT_ONLY_ADAPTER_DISABLED_USE_VERIFIED_CANARY')
        folder = owned(folder); folder.mkdir(parents=True, exist_ok=True)
        execution = task['execution_ref']
        if execution in self.handles: raise RuntimeError('Execution already owned')
        
        prompt_text = task.get('request', {}).get('prompt', 'Complete the task.')
        atomic(folder / 'prompt.txt', prompt_text)
        
        env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH'}}
        
        # muse exec arguments
        command = [
            'muse', 'exec', '--json',
            '--prompt-file', str(folder / 'prompt.txt'),
            '--workspace', str(self.workspace),
            '--no-foreign-personal-context',
            '--no-session-log',
            '--session-id', execution,
            '--provider', 'echo'
        ]
        
        child, job, identity = launch_gated(command, str(self.workspace), env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.handles[execution] = (child, job)
        
        identity.update(task_id=task['task_id'], attempt_id=task['attempt_id'], execution_id=execution,
                        dispatch_id=task['dispatch_id'], worker_id=task['worker_id'])
                        
        try:
            atomic(folder / 'process.json', identity)
            persist_identity(identity)
            if child.stdin: child.stdin.close()
            
            import threading
            import json
            def consume_output():
                final_result = None
                with open(folder / 'event.json', 'w', encoding='utf-8') as f:
                    for line in child.stdout:
                        try:
                            decoded = line.decode('utf-8')
                            f.write(decoded)
                            data = json.loads(decoded)
                            if data.get('payload_type') == 'run.terminal.completed':
                                final_result = data
                        except Exception:
                            pass
                
                # Consume stderr as well to prevent blocking
                for line in child.stderr: pass
                
                # child is terminating, wait for it
                child.wait()
                status = 'SUCCESS' if child.returncode == 0 else 'FAILED'
                
                # Construct result based on what verify_result expects
                raw = dict(task)
                raw['status'] = status
                raw['run_id'] = f"muse-run-{execution}"
                
                # Write to result.json
                atomic(folder / 'result.json', raw)
                
            threading.Thread(target=consume_output, daemon=True).start()
            
        except BaseException:
            self.close_execution(execution); raise
        return child

    def result(self, task, folder):
        raw = read(owned(folder) / 'result.json')
        if not raw: raise ValueError('MISSING_RESULT')
        # The contract verify_result generates the final canonical DurableResult payload
        verified = self.contract.verify_result(task, raw, self.workspace)
        return self.contract.validate_durable_result(task, verified)

    def cancel(self, execution_id):
        child, _ = self.handles.get(execution_id, (None, None))
        if child and child.poll() is None:
            try: child.terminate()
            except OSError: pass

    def close_execution(self, execution_id):
        entry = self.handles.pop(execution_id, None)
        if not entry: return
        child, job = entry
        try:
            if child.poll() is None: child.kill()
            child.wait(timeout=5)
        finally:
            job.close()
            if child.stdin: child.stdin.close()

    def close(self):
        for execution in list(self.handles):
            self.close_execution(execution)
