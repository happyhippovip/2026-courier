"""Local test process. Never launches Muse, a provider, shell, or network call."""
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path
from .storage import atomic, owned


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if os.read(0, 3) != b'GO\n':
        return 2
    cancel = threading.Event()
    def listen():
        if os.read(0, 32).strip() == b'CANCEL':
            cancel.set()
    threading.Thread(target=listen, daemon=True).start()
    spec = importlib.util.spec_from_file_location('canonical_contract', request['contract'])
    contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)
    task = request['task']; mode = request['mode']; start = time.time()
    workspace = owned(request['workspace'])
    if mode == 'TIMEOUT':
        cancel.wait(60)
    else:
        cancel.wait(request['delay'])
    event = {'pid': os.getpid(), 'task_id': task['task_id'], 'attempt_id': task['attempt_id'],
             'execution_ref': task['execution_ref'], 'start': start, 'end': time.time(), 'mode': mode}
    atomic(request['events'], event)
    if mode == 'MALFORMED_RESULT':
        atomic(request['result'], {'status': 'SUCCESS', 'unbound': True})
        return 0
    failed = cancel.is_set() or mode in {'FAILURE', 'CANCEL'}
    raw = {key: task[key] for key in ('goal_id', 'task_id', 'attempt_id', 'dispatch_id', 'execution_ref', 'worker_id')}
    raw.update(status='FAILED' if failed else 'SUCCESS', run_id=f'fake-pid-{os.getpid()}')
    for key in ('batch_id', 'prompt_id'):
        if key in task: raw[key] = task[key]
    if not failed:
        for name in task.get('artifacts', []):
            target = (workspace / name).resolve()
            if not target.is_relative_to(workspace) or target == workspace:
                return 4
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x', encoding='utf-8', newline='\n') as output:
                output.write(task['instruction'] + '\n'); output.flush(); os.fsync(output.fileno())
    result = contract.verify_result(task, raw, workspace)
    if failed:
        result['stderr'] = '[TIMEOUT/HANG] fake deadline' if mode == 'TIMEOUT' else 'Fake worker: cancelled' if cancel.is_set() or mode == 'CANCEL' else 'Deterministic fake failure'
    atomic(request['result'], result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
