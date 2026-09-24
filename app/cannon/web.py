import os
import subprocess
import sys
from pathlib import Path
import threading
from .cli import build_identity
from .processes import launch_gated
import json

from .storage import atomic, owned, read

ROOT = Path(__file__).resolve().parent.parent.parent
MAC_ADAPTER = ROOT / 'scripts' / 'mac_adapter.py'
DEMO = owned(os.environ['CANNON_DEMO_DIR']) if os.environ.get('CANNON_DEMO_DIR') else None
ACTIVE_DEMO = None
LOADED_BUILD = build_identity()
LOCK = threading.Lock()
CHILD = None
JOB = None


def _demo_env(target: Path) -> dict:
    env = dict(os.environ)
    env['CANNON_DEMO_DIR'] = str(target)
    env['CANNON_ENFORCE_COOLDOWN'] = '1'
    extra_paths = [str(ROOT / 'app'), str(ROOT), str(ROOT / '.venv/Lib/site-packages')]
    shared_venv = ROOT.parents[2] / '2026-courier/.venv/Lib/site-packages' if len(ROOT.parents) >= 3 else None
    if shared_venv and shared_venv.exists():
        extra_paths.append(str(shared_venv))
    existing = env.get('PYTHONPATH', '')
    if existing:
        extra_paths.append(existing)
    env['PYTHONPATH'] = os.pathsep.join(extra_paths)
    return env


def demo_path(count=5, mode='NORMAL'):
    base = Path(DEMO) if DEMO is not None else (ROOT / 'data/cannon-demo')
    norm_mode = 'NORMAL' if mode == 'BEGRENZT' else str(mode)
    return owned(base / f'{norm_mode.lower()}-{count}')


def active_demo():
    if DEMO is not None:
        info = read(owned(Path(DEMO) / 'active.json'), None)
        if isinstance(info, dict) and info.get('path'):
            return owned(info['path'])
        return None
    return ACTIVE_DEMO


def get_mac_status():
    try:
        out = subprocess.check_output([sys.executable, str(MAC_ADAPTER), "status"], text=True)
        return json.loads(out)
    except Exception:
        return {}

def status():
    global CHILD, JOB
    with LOCK:
        if CHILD is not None and CHILD.poll() is not None:
            if JOB: JOB.close(); JOB = None
            if CHILD.stdin: CHILD.stdin.close()
        helper_active = CHILD is not None and CHILD.poll() is None

        if DEMO is not None:
            cur = active_demo()
            default_state = {'status': 'NOT_STARTED', 'metrics': {}, 'counts': {}, 'lanes': {}, 'active_lanes': 0}
            st_obj = read(cur / 'controller/controller.json', default_state) if cur else default_state
            sess_obj = read(cur / 'session.json', {}) if cur else {}
            err_obj = read(cur / 'error.json', None) if cur else None
            return {
                'kind': 'FAKE_CORE_FIXTURE',
                'live_muse': 'UNPROVEN',
                'workspace': str(cur / 'workspace') if cur else str(ROOT),
                'demo_directory': str(cur) if cur else str(DEMO),
                'independent_acceptance': 'PENDING',
                'loaded_build': LOADED_BUILD,
                'source_build': build_identity(),
                'helper_active': helper_active,
                'helper_exit': CHILD.poll() if CHILD is not None else 0,
                'session': sess_obj,
                'error': err_obj.get('error') if isinstance(err_obj, dict) else None,
                'state': st_obj,
            }
        
        mac = get_mac_status()
        ov = mac.get('overnight', {})
        tc = mac.get('task_counts', {})
        inv = mac.get('invariants', {})
        
        # Translate mac_adapter status to cannon.js expectations
        is_active = mac.get('state') in ('RUNNING', 'STOP_AFTER_CURRENT')
        
        st = mac.get('state', 'IDLE')
        if st == 'COMPLETED': st = 'COMPLETED'
        elif st == 'ERROR': st = 'ERROR'
        elif st == 'PAUSED': st = 'PAUSED'
        elif st == 'STOP_AFTER_CURRENT': st = 'IDLE'
        elif st == 'IDLE': st = 'IDLE'
        elif is_active: st = 'RUNNING'
        
        mode = ov.get('laufart', 'BEGRENZT')
        count = ov.get('verbleibend', 0)
        if count == '∞': count = 1000000
        
        lanes = {}
        if is_active:
            lanes['worker-1'] = {'phase': 'RUNNING', 'task': {'task_id': mac.get('current_task')}}
            
        return {
            'kind': 'MAC_ADAPTER',
            'live_muse': 'UNPROVEN',
            'workspace': str(ROOT),
            'demo_directory': str(ROOT),
            'independent_acceptance': 'PENDING',
            'loaded_build': LOADED_BUILD,
            'source_build': build_identity(),
            'helper_active': helper_active,
            'helper_exit': CHILD.poll() if CHILD is not None else None,
            'session': {'count': count, 'mode': mode},
            'error': None,
            'state': {
                'status': st,
                'metrics': {'DONE': inv.get('DONE', 0)},
                'counts': {'QUEUED': tc.get('READY', 0), 'RESULT_RECEIVED': tc.get('WAITING', 0)},
                'lanes': lanes,
                'active_lanes': 1 if is_active else 0,
                'last_result': ov.get('letztes_ergebnis')
            }
        }

def action(body):
    global CHILD, JOB, ACTIVE_DEMO
    action_type = body.get('action')
    if action_type not in {'START', 'RESUME', 'PAUSE', 'STOP_AFTER_CURRENT'}:
        raise ValueError('Unknown Cannon action')
        
    with LOCK:
        active = CHILD is not None and CHILD.poll() is None
        if action_type in {'PAUSE', 'STOP_AFTER_CURRENT'}:
            if DEMO is not None:
                cur = active_demo()
                if cur is not None:
                    atomic(cur / 'controller/control.json', {'action': action_type})
                return {'ok': True}
            if action_type == 'PAUSE':
                subprocess.check_call([sys.executable, str(MAC_ADAPTER), "pause"])
            else:
                subprocess.check_call([sys.executable, str(MAC_ADAPTER), "stop"])
            return {'ok': True}

        if build_identity() != LOADED_BUILD:
            raise ValueError('Neue Version vorhanden: Bitte Server neu starten')

        if action_type == 'START':
            count = body.get('count', 5)
            mode = body.get('mode', 'BEGRENZT')
            if mode not in {'NORMAL', 'BEGRENZT', 'UNENDLICH'}:
                raise ValueError(f'Invalid mode: {mode}')
            if isinstance(count, bool) or not isinstance(count, int) or count < 1 or count > 100:
                raise ValueError(f'Invalid count: {count}')
            if active:
                return {'ok': True, 'already_running': True, 'reused': True}
            
            if JOB: JOB.close(); JOB = None
            if CHILD is not None and CHILD.stdin: CHILD.stdin.close()

            if DEMO is not None:
                norm_mode = 'NORMAL' if mode == 'BEGRENZT' else mode
                target = demo_path(count, norm_mode)
                target.mkdir(parents=True, exist_ok=True)
                ACTIVE_DEMO = target
                atomic(Path(DEMO) / 'active.json', {'path': str(target), 'count': count, 'mode': norm_mode})
                atomic(target / 'controller/control.json', {'action': 'RESUME'})
                env = _demo_env(target)
                command = [sys.executable, '-m', 'cannon.cli', 'demo', '--count', str(count), '--mode', norm_mode, '--gated']
                CHILD, JOB, _ = launch_gated(command, str(ROOT), env, stderr=subprocess.PIPE)
                if CHILD.stdin:
                    try:
                        CHILD.stdin.write(b'GO\n')
                        CHILD.stdin.flush()
                    except Exception:
                        pass
                def bounded_errors(child):
                    if getattr(child, 'stderr', None):
                        for chunk in iter(lambda: child.stderr.read(1024), b''):
                            pass
                threading.Thread(target=bounded_errors, args=(CHILD,), daemon=True).start()
                return {'ok': True, 'reused': False}
            
            art = "unendlich" if mode == "UNENDLICH" else "begrenzt"
            command = [sys.executable, str(MAC_ADAPTER), "dauerlauf", "--art", art, "--local-fake"]
            if art == "begrenzt":
                command += ["--limit", str(count)]
            CHILD, JOB, _ = launch_gated(command, str(ROOT), dict(os.environ), stderr=subprocess.PIPE)
            
            def bounded_errors(child):
                for chunk in iter(lambda: child.stderr.read(1024), b''):
                    pass
            threading.Thread(target=bounded_errors, args=(CHILD,), daemon=True).start()
            
            return {'ok': True, 'reused': False}
            
        if action_type == 'RESUME':
            if DEMO is not None:
                cur = active_demo()
                if cur is None or (not (cur / 'session.json').exists() and not (cur / 'controller/controller.json').exists()):
                    raise ValueError('No active session to resume')
                sess = read(cur / 'session.json', {}) or {}
                resume_count = sess.get('count', 5)
                resume_mode = sess.get('mode', 'NORMAL')
                atomic(cur / 'controller/control.json', {'action': 'RESUME'})
                if not active:
                    env = _demo_env(cur)
                    command = [sys.executable, '-m', 'cannon.cli', 'demo', '--count', str(resume_count), '--mode', str(resume_mode), '--gated']
                    CHILD, JOB, _ = launch_gated(command, str(ROOT), env, stderr=subprocess.PIPE)
                    if CHILD.stdin:
                        try:
                            CHILD.stdin.write(b'GO\n')
                            CHILD.stdin.flush()
                        except Exception:
                            pass
                    def bounded_errors(child):
                        if getattr(child, 'stderr', None):
                            for chunk in iter(lambda: child.stderr.read(1024), b''):
                                pass
                    threading.Thread(target=bounded_errors, args=(CHILD,), daemon=True).start()
                return {'ok': True}
            subprocess.check_call([sys.executable, str(MAC_ADAPTER), "resume"])
            if not active:
                # if not active, we need to spawn it again to continue supervision
                command = [sys.executable, str(MAC_ADAPTER), "dauerlauf", "--art", "begrenzt", "--limit", "1000000", "--local-fake"]
                CHILD, JOB, _ = launch_gated(command, str(ROOT), dict(os.environ), stderr=subprocess.PIPE)
                def bounded_errors(child):
                    for chunk in iter(lambda: child.stderr.read(1024), b''):
                        pass
                threading.Thread(target=bounded_errors, args=(CHILD,), daemon=True).start()
            return {'ok': True}

def close():
    global CHILD, JOB
    with LOCK:
        if JOB: JOB.close(); JOB = None
        if CHILD:
            try: CHILD.wait(timeout=5)
            except Exception: CHILD.kill(); CHILD.wait(timeout=5)
            if CHILD.stdin: CHILD.stdin.close()
