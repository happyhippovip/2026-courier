"""Bounded lane lifecycle. Canonical claim and verified state remain Courier-owned."""
import ctypes
import os
import queue
import threading
import time
from .storage import InstanceLock, atomic, digest, owned, read

MAX_ACTIVE_EXTERNAL = 1
MAX_UNANSWERED_PROMPTS_PER_LANE = 1
NEXT_TASK_COOLDOWN_SECONDS = 5


def resource_state():
    try:
        import psutil
        import sys
        mem = psutil.virtual_memory()
        if sys.platform == 'darwin':
            if mem.available < 512 * 1024**2: return 'RED'
            if mem.available < 1024**3: return 'YELLOW'
            return 'GREEN'
        if mem.percent >= 90 or mem.available < 512 * 1024**2: return 'RED'
        if mem.percent >= 75 or mem.available < 1024**3: return 'YELLOW'
        return 'GREEN'
    except Exception:
        return 'GREEN'


class Controller:
    def __init__(self, root, core, adapter, mode='NORMAL', resources=resource_state, timeout=10):
        self.root, self.core, self.adapter = owned(root), core, adapter
        if mode != 'NORMAL': raise ValueError('V0 Dauerlauf requires NORMAL with one active execution')
        if adapter.discover().get('kind') == 'FAKE_PROCESS' and not core.isolated:
            raise ValueError('Fake results must never enter production Courier')
        self.mode, self.width, self.resources, self.timeout = mode, MAX_ACTIVE_EXTERNAL, resources, timeout
        self.events = queue.Queue()
        self.state = read(self.root / 'controller.json', {'schema': 1, 'lanes': {}, 'metrics': {
            'STARTED': 0, 'DONE': 0, 'FAILED': 0, 'RESOURCE_PAUSES': 0, 'HUMAN_RELAY_COUNT': 0}, 'status': 'IDLE'})
        if self.state.get('schema') != 1: raise ValueError('Unknown operational checkpoint')
        self.active = {}
        self.last_resource = None
        self.cooldown_deadline = 0

    def save(self):
        self.state.update(mode=self.mode, active_lanes=len(self.active),
                          max_active_external=MAX_ACTIVE_EXTERNAL,
                          max_unanswered_prompts_per_lane=MAX_UNANSWERED_PROMPTS_PER_LANE,
                          next_task_cooldown_seconds=NEXT_TASK_COOLDOWN_SECONDS)
        atomic(self.root / 'controller.json', self.state)

    def control(self, action):
        if action not in {'RUN', 'PAUSE', 'RESUME', 'STOP_AFTER_CURRENT'}: raise ValueError('Invalid control')
        atomic(self.root / 'control.json', {'action': action})
        self.events.put(('control', None))

    def _await_child(self, worker, execution, child):
        try:
            child.wait(timeout=self.timeout)
        except Exception:
            self.adapter.cancel(execution)
            try: child.wait(timeout=2)
            except Exception: self.adapter.close_execution(execution)
        self.events.put(('finished', worker))

    def _finish(self, worker):
        lane = self.state['lanes'][worker]
        task = lane['task']
        try:
            result = self.adapter.result(task, lane['folder'])
            atomic(owned(lane['folder']) / 'outbox.json', result)
            lane['phase'] = 'RESULT_STAGED'; self.save()
            self.core.receive(result)
            lane['phase'] = 'AWAITING_VERIFICATION'; self.save()
            self.core.after_result()
        except Exception as exc:
            lane.update(phase='UNKNOWN', reason=str(exc)[:300])
        finally:
            self.active.pop(worker, None)
            self.adapter.close_execution(task['execution_ref'])
            self.save()

    def _reconcile_lanes(self):
        def exact_receipt(lane, task, result):
            self.adapter.contract.validate_durable_result(lane['task'], result)
            # Core may clear worker_id while queueing a failed attempt for retry.
            # The immutable execution tuple and stored receipt must still match.
            for key in ('goal_id', 'task_id', 'attempt_id', 'dispatch_id', 'execution_ref'):
                if task.get(key) != lane['task'].get(key):
                    raise ValueError('Canonical attempt changed before lane reconciliation')
            if any(task.get('result', {}).get(key) != value for key, value in result.items()):
                raise ValueError('Canonical receipt no longer matches owned result')
        for worker, lane in self.state['lanes'].items():
            if lane['phase'] in {'IDLE', 'ERROR'}: continue
            if lane['phase'] == 'UNKNOWN' and (owned(lane['folder']) / 'outbox.json').is_file():
                # A lost HTTP ACK is not a new execution. Only exact canonical
                # receipt evidence may resolve this ambiguity after restart.
                try:
                    result = read(owned(lane['folder']) / 'outbox.json')
                    task = self.core.task(lane['task']['task_id'])
                    exact_receipt(lane, task, result)
                    lane['phase'] = 'AWAITING_VERIFICATION'
                    self.core.after_result()
                except Exception:
                    pass  # Preserve the original UNKNOWN reason and lane lock.
            if lane['phase'] in {'INTENT', 'RUNNING'} and worker not in self.active:
                # Windows job closed on owner death. A durable worker result may
                # still exist; otherwise UNKNOWN is retained, never relaunched.
                if (owned(lane['folder']) / 'result.json').is_file():
                    self._finish(worker)
                else:
                    lane.update(phase='UNKNOWN', reason='OWNER_RESTART_WITHOUT_DURABLE_RESULT')
            elif lane['phase'] == 'RESULT_STAGED':
                try:
                    result = read(owned(lane['folder']) / 'outbox.json')
                    self.adapter.contract.validate_durable_result(lane['task'], result)
                    self.core.receive(result)
                    lane['phase'] = 'AWAITING_VERIFICATION'
                    self.core.after_result()
                except Exception as exc:
                    lane.update(phase='UNKNOWN', reason=str(exc)[:300])
            if lane['phase'] != 'AWAITING_VERIFICATION': continue
            task = self.core.task(lane['task']['task_id'])
            expected = read(owned(lane['folder']) / 'outbox.json')
            try:
                exact_receipt(lane, task, expected)
            except (ValueError, TypeError) as exc:
                lane.update(phase='UNKNOWN', reason=str(exc)[:300]); continue
            # Never equate subprocess exit / worker SUCCESS / HTTP 200 with DONE.
            if (task.get('status') == 'RECONCILED' and task.get('verification', {}).get('verdict') == 'PASS'
                    and task.get('verification', {}).get('result_id') == expected['result_id']):
                # Start the cooldown only after durable, exact, verified completion.
                # This record is independent of subprocess exit and worker SUCCESS.
                confirmed = time.time()
                completion = {key: lane['task'][key] for key in
                              ('goal_id', 'task_id', 'attempt_id', 'dispatch_id', 'execution_ref')}
                completion.update(result_id=expected['result_id'], confirmed_at=confirmed,
                                  next_task_not_before=confirmed + NEXT_TASK_COOLDOWN_SECONDS)
                atomic(owned(lane['folder']) / 'completion.json', completion)
                self.state['last_completion'] = completion
                self.cooldown_deadline = time.monotonic() + NEXT_TASK_COOLDOWN_SECONDS
                self.state['metrics']['DONE'] += 1
            elif task.get('status') in {'QUEUED', 'FAILED_TERMINAL', 'FAILED_VERIFICATION', 'HUMAN_REQUIRED'}:
                self.state['metrics']['FAILED'] += 1
                lane.update(phase='ERROR', reason='RESULT_REQUIRES_INTERVENTION: ' + task['status'])
            else:
                continue
            atomic(owned(lane['folder']) / 'observed-core.json', task)
            self.state['last_result'] = {'task_id': task['task_id'], 'result_id': task.get('result', {}).get('result_id'), 'status': task['status']}
            if lane['phase'] != 'ERROR': self.state['lanes'][worker] = {'phase': 'IDLE'}
            self.save()

    def run(self, max_starts=None):
        if max_starts is not None and not 1 <= max_starts <= 100: raise ValueError('Invalid explicit start budget')
        with InstanceLock(self.root):
            # A controller object may have been constructed before another run
            # finished. Refresh only after exclusive ownership is established.
            self.state = read(self.root / 'controller.json', self.state)
            # Monotonic clocks cannot cross processes. On restart impose a fresh
            # full cooldown if a completion exists, conservatively surviving clock jumps.
            if self.state.get('last_completion'):
                self.cooldown_deadline = time.monotonic() + NEXT_TASK_COOLDOWN_SECONDS
            initial = self.state['metrics']['STARTED']
            self.state['status'] = 'RUNNING'; self.save()
            try:
                while True:
                    self._reconcile_lanes()
                    action = read(self.root / 'control.json', {'action': 'RUN'})['action']
                    resource = self.resources()
                    if resource not in {'GREEN', 'YELLOW', 'RED'}: resource = 'YELLOW'
                    self.state['resource'] = resource
                    if resource != 'GREEN' and self.last_resource != resource:
                        self.state['metrics']['RESOURCE_PAUSES'] += 1
                    self.last_resource = resource
                    tasks = self.core.tasks()  # bounded selected goals only
                    self.state['counts'] = {s: sum(t.get('status') == s for t in tasks) for s in sorted({t.get('status', 'UNKNOWN') for t in tasks})}
                    ready_hint = any(t.get('status') == 'QUEUED' and t.get('next_retry_at', 0) <= time.time() for t in tasks)
                    lanes_clear = not self.active and all(l['phase'] == 'IDLE' for l in self.state['lanes'].values())
                    available = self.adapter.health().get('available') is True
                    budget = max_starts is None or self.state['metrics']['STARTED'] - initial < max_starts
                    may_start = action in {'RUN', 'RESUME'} and resource == 'GREEN' and available and lanes_clear and budget
                    cooldown = max(0, self.cooldown_deadline - time.monotonic())
                    if may_start and ready_hint and cooldown > 0:
                        self.state['status'] = 'COOLDOWN'; self.save()
                        # One local timed wait. Completion was already verified;
                        # timeout only permits re-evaluating readiness and controls.
                        try: self.events.get(timeout=cooldown)
                        except queue.Empty: pass
                        continue
                    if may_start and ready_hint:
                        for index in range(self.width):
                            worker = self.core.worker_ids[index]
                            lane = self.state['lanes'].setdefault(worker, {'phase': 'IDLE'})
                            if lane['phase'] != 'IDLE': continue
                            # Core alone decides dependencies, gates, scope locks and eligibility.
                            task = self.core.claim(worker)
                            if not task: continue
                            folder = self.root / 'executions' / digest(task['execution_ref'])
                            if folder.exists():
                                lane.update(phase='UNKNOWN', reason='EXECUTION_ID_ALREADY_OBSERVED', task=task, folder=str(folder)); continue
                            lane.update(phase='INTENT', task=task, folder=str(folder)); self.save()
                            def persist(identity, lane=lane):
                                lane.update(process=identity, phase='RUNNING')
                                self.state['metrics']['STARTED'] += 1; self.save()
                            try:
                                child = self.adapter.execute(task, folder, persist)
                                self.active[worker] = child
                                threading.Thread(target=self._await_child, args=(worker, task['execution_ref'], child), daemon=True).start()
                            except Exception as exc:
                                lane.update(phase='UNKNOWN', reason=str(exc)[:300])
                    if not self.active:
                        phases = [l['phase'] for l in self.state['lanes'].values()]
                        if any(p not in {'IDLE', 'ERROR'} for p in phases): status = 'RECONCILE_REQUIRED'
                        elif 'ERROR' in phases: status = 'BLOCKED'
                        elif action == 'PAUSE': status = 'PAUSED'
                        elif action == 'STOP_AFTER_CURRENT': status = 'IDLE'
                        elif resource != 'GREEN': status = 'CANNON_PAUSED_RESOURCE'
                        elif ready_hint and not available: status = 'BLOCKED_UNAVAILABLE'
                        elif any(t.get('status') not in {'RECONCILED', 'FAILED_TERMINAL', 'FAILED_VERIFICATION'} for t in tasks): status = 'WAITING'
                        else: status = 'IDLE'
                        self.state['status'] = status; self.save()
                        return self.state
                    self.state['status'] = 'RUNNING'; self.save()
                    # Sleep on OS process completion/control events. No LLM or idle poll.
                    event, worker = self.events.get()
                    if event == 'finished': self._finish(worker)
            finally:
                self.adapter.close()
                self.save()
