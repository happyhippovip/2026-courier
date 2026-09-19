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
        return {'kind': 'MUSE', 'state': 'CLI_EXEC_CONFIRMED',
                'version': '1.3.0-R3401.1', 'command': 'muse exec --json --prompt-file PATH',
                'evidence': ['data/muse-cli-help.txt', 'data/muse-exec-help.txt', 'data/muse-cli-version.txt'],
                'execution': 'PROVEN'}

    def health(self):
        return {'available': True, 'state': 'CLI_EXEC_CONFIRMED', 'kind': 'MUSE'}

    def execute(self, task, folder, persist_identity):
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