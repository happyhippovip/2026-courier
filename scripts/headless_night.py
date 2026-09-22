"""Headless night runtime policy around the proven single-task engine.

The engine (scripts/cannon_motor.py run_step: claim -> execute -> complete ->
verify -> reconcile -> DONE -> cooldown) is reused unchanged. This module adds
only the outer indefinite repetition: calm waiting, BRAUCHT_DICH stops,
sleep prevention, and the headless muse command policy.

No provider calls happen at import. Live execution happens only when the
caller explicitly runs a REAL_MUSE task through the motor.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SYS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SYS_ROOT))

COOLDOWN_SECONDS = 5
MAX_ACTIVE_EXTERNAL = 1

# Conservative pre-submission failure hints. Best effort only: anything
# unmatched stays UNKNOWN (fail closed, never retried, never advanced).
WAIT_HINTS = re.compile(
    r'rate.?limit|429|quota|insufficient|credit|exhaust|payment|'
    r'temporar\w* unavailable|503|overload|try again later|timeout',
    re.IGNORECASE)


def build_command(executable, provider='meta', workspace='.', prompt_file=None,
                  reasoning_effort='low', max_model_steps=6):
    """Headless muse command from flags supported by the installed CLI.

    Approval prompts are off for the unattended runtime; the sandbox stays
    on (never --yolo, never --disable-sandbox).
    """
    command = [executable, 'exec', '--json', '--provider', provider,
               '--reasoning-effort', reasoning_effort,
               '--max-model-steps', str(max_model_steps),
               '--workspace', str(workspace), '--disable-approval',
               '--no-foreign-personal-context', '--no-session-log']
    if prompt_file is not None:
        command += ['--prompt-file', str(prompt_file)]
    return command


def check_command_policy(command):
    """Fail closed when the unattended policy is violated."""
    if '--disable-approval' not in command:
        raise ValueError('APPROVAL_PROMPTS_REQUIRED')
    if '--yolo' in command or '--disable-sandbox' in command:
        raise ValueError('SANDBOX_DISABLED')
    if '--json' not in command:
        raise ValueError('NO_EVENT_STREAM')
    if '--workspace' not in command:
        raise ValueError('NO_WORKSPACE')
    return True


def parse_events(raw):
    """Parse a JSONL stream. Returns (events, malformed_count)."""
    events = []
    malformed = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            malformed += 1
    return events, malformed


def has_terminal(events):
    return any(isinstance(e, dict) and e.get('payload_type') == 'run.terminal.completed'
               for e in events)


def classify_result(events, malformed, exit_code, stderr=''):
    """Exit code alone never means success.

    Returns (verdict, reason) with verdict in ok | NO_SUCCESS | UNKNOWN | WAIT_RETRY.
    """
    if not events and malformed == 0:
        if exit_code == 0:
            return 'NO_SUCCESS', 'EMPTY_OUTPUT'
        if WAIT_HINTS.search(stderr or ''):
            return 'WAIT_RETRY', 'PRE_SUBMISSION_FAILURE'
        return 'UNKNOWN', 'NO_EVENTS_NONZERO_EXIT'
    if malformed > 0:
        return 'NO_SUCCESS', 'MALFORMED_OUTPUT'
    if not has_terminal(events):
        if exit_code != 0 and WAIT_HINTS.search(stderr or ''):
            return 'WAIT_RETRY', 'PRE_SUBMISSION_FAILURE'
        return 'UNKNOWN', 'AMBIGUOUS_NO_TERMINAL'
    return 'OK_PENDING_PAYLOAD', 'TERMINAL_EVENT_PRESENT'


def _kill_child(child):
    try:
        child.kill()
    except Exception:
        pass
    try:
        child.wait(timeout=5)
    except Exception:
        pass


def _stream_with_timeouts(child, timeout, idle_timeout):
    """Wall-clock AND idle-output timeouts. A silent hung child is killed.

    Returns (stdout_bytes, stderr_bytes). Raises TimeoutError on either
    deadline. Falls back to communicate() where select is unavailable.
    """
    import os
    import select as select_module
    import time as time_module
    for stream in (child.stdout, child.stderr):
        try:
            os.set_blocking(stream.fileno(), False)
        except Exception:
            out, err = child.communicate(timeout=timeout)
            return out, err
    out_chunks, err_chunks = [], []
    open_streams = {child.stdout, child.stderr}
    start = time_module.monotonic()
    last_output = start
    while open_streams:
        now = time_module.monotonic()
        if now - start >= timeout:
            _kill_child(child)
            raise TimeoutError('MUSE_TIMEOUT_UNKNOWN_EFFECT')
        if now - last_output >= idle_timeout:
            _kill_child(child)
            raise TimeoutError('MUSE_IDLE_TIMEOUT_UNKNOWN_EFFECT')
        quantum = max(0.05, min(0.5, idle_timeout - (now - last_output),
                                timeout - (now - start)))
        try:
            ready, _, _ = select_module.select(list(open_streams), [], [], quantum)
        except (ValueError, OSError):
            break
        if not ready and child.poll() is not None:
            for stream in list(open_streams):
                try:
                    data = stream.read()
                except Exception:
                    data = b''
                if data:
                    (out_chunks if stream is child.stdout else err_chunks).append(data)
                    last_output = time_module.monotonic()
                open_streams.discard(stream)
            continue
        for stream in ready:
            try:
                data = stream.read(65536)
            except Exception:
                data = b''
            if data:
                (out_chunks if stream is child.stdout else err_chunks).append(data)
                last_output = time_module.monotonic()
            else:
                open_streams.discard(stream)
    try:
        child.wait(timeout=5)
    except Exception:
        _kill_child(child)
    return b''.join(out_chunks), b''.join(err_chunks)


def run_headless(command, cwd='.', timeout=90, idle_timeout=30,
                 spawn=subprocess.Popen):
    """Run one headless muse execution. stdin is always DEVNULL (never interactive)."""
    check_command_policy(command)
    with open('/dev/null', 'rb') as devnull:
        child = spawn(command, stdin=devnull, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE, cwd=str(cwd), env=dict(__import__('os').environ))
        out, err = _stream_with_timeouts(child, timeout, idle_timeout)
    raw = out.decode('utf-8', 'replace') if isinstance(out, bytes) else out
    events, malformed = parse_events(raw)
    verdict, reason = classify_result(events, malformed, child.returncode,
                                      err.decode('utf-8', 'replace') if isinstance(err, bytes) else err)
    return {'exit_code': child.returncode, 'events': events,
            'malformed': malformed, 'verdict': verdict, 'reason': reason}


class CaffeinateGuard:
    """Hold a macOS idle-sleep assertion for the run; release it after.

    No daemon, no root. No-op where caffeinate is unavailable.
    """

    def __init__(self, spawn=subprocess.Popen):
        self._spawn = spawn
        self._child = None

    def __enter__(self):
        if shutil.which('caffeinate') is None:
            return {'sleep_prevention': 'UNAVAILABLE'}
        self._child = self._spawn(['caffeinate', '-i'],
                                  stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        return {'sleep_prevention': 'CAFFEINATE_IDLE'}

    def __exit__(self, *exc):
        child, self._child = self._child, None
        if child is not None:
            try:
                child.terminate()
                child.wait(timeout=5)
            except Exception:
                try:
                    child.kill()
                except Exception:
                    pass
        return False


def _ready_tasks(motor):
    try:
        snap = motor.queue_snapshot()
    except Exception:
        return False
    tasks = (snap or {}).get('tasks', {})
    return any(((info or {}).get('status') in ('READY', 'WAITING'))
               for info in tasks.values())


def night_loop(state_dir, idle_backoff=30.0, supervise_cycles=1000,
               max_iterations=None, sleep=time.sleep, on_cycle=None):
    """Repeat the proven single-task engine until a real stop reason exists.

    Returns a handoff dict; never invents work, never busy-loops:
    - BLOCKED / ERROR / needs_review -> BRAUCHT_DICH, no next task, no retry.
    - stop requested -> clean STOPPED_AFTER_CURRENT.
    - PAUSED or no READY work -> calm wait, then re-evaluate.
    - READY work while idle -> re-arm through motor.start(), never by hand.
    """
    from scripts.cannon_motor import CannonMotor
    motor = CannonMotor(state_dir)
    iterations = 0
    with CaffeinateGuard():
        while True:
            if max_iterations is not None and iterations >= max_iterations:
                motor._load()
                return {'status': 'ITERATION_BUDGET', 'done': motor.m['done_count']}
            iterations += 1
            motor._load()
            if motor.m.get('needs_review') or motor.m['state'] in ('ERROR', 'BLOCKED'):
                return {'status': 'BRAUCHT_DICH', 'done': motor.m['done_count'],
                        'review': list(motor.m.get('needs_review', [])),
                        'error': motor.m.get('error'), 'retry': False,
                        'next_task': False}
            if motor.m.get('stop_requested'):
                return {'status': 'STOPPED_AFTER_CURRENT', 'done': motor.m['done_count']}
            if motor.m['state'] == 'PAUSED':
                sleep(idle_backoff)
                continue
            if motor.m['state'] not in ('RUNNING', 'STOP_AFTER_CURRENT'):
                if not _ready_tasks(motor):
                    if on_cycle is not None:
                        on_cycle(motor)
                    sleep(idle_backoff)
                    continue
                started = motor.start(
                    cooldown=motor.m.get('cooldown_seconds', COOLDOWN_SECONDS),
                    local_fake=motor.m.get('local_fake', False),
                    continuous_canary=motor.m.get('continuous_canary', False))
                if not started.get('started'):
                    if started.get('reason') == 'review_required':
                        return {'status': 'BRAUCHT_DICH', 'done': motor.m['done_count'],
                                'review': list(motor.m.get('needs_review', [])),
                                'error': motor.m.get('error'), 'retry': False,
                                'next_task': False}
                    sleep(idle_backoff)
                    continue
            motor.supervise(max_cycles=supervise_cycles)
