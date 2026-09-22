import os
import subprocess
import sys
from pathlib import Path
import threading
from .cli import build_identity
from .processes import launch_gated
import json

ROOT = Path(__file__).resolve().parent.parent.parent
MAC_ADAPTER = ROOT / 'scripts' / 'mac_adapter.py'
LOADED_BUILD = build_identity()
LOCK = threading.Lock()
CHILD = None
JOB = None

# Billion countdown: display ceiling only, never preallocated.
# Remaining = TARGET - (verified DONE since START).
RUN_TARGET = 1000000000
RUN_BASE = {"done": None}


def _current_done():
    try:
        mac = get_mac_status()
        return int(mac.get("overnight", {}).get("erledigt", 0))
    except Exception:
        return 0

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
        
        mac = get_mac_status()
        ov = mac.get('overnight', {})
        tc = mac.get('task_counts', {})
        inv = mac.get('invariants', {})
        
        # Translate mac_adapter status to cannon.js expectations
        current_task = mac.get('current_task')
        motor_running = mac.get('state') in ('RUNNING', 'STOP_AFTER_CURRENT')
        is_active = motor_running and bool(current_task)
        helper_active = CHILD is not None and CHILD.poll() is None
        
        st = mac.get('state', 'IDLE')
        if st == 'COMPLETED': st = 'COMPLETED'
        elif st == 'ERROR': st = 'ERROR'
        elif st == 'PAUSED': st = 'PAUSED'
        elif st == 'STOP_AFTER_CURRENT': st = 'IDLE'
        elif st == 'IDLE': st = 'IDLE'
        elif is_active: st = 'RUNNING'
        elif helper_active and motor_running and not current_task:
            st = 'WAITING'
        
        mode = ov.get('laufart', 'BEGRENZT')
        count = ov.get('verbleibend', 0)
        if count == '∞': count = 1000000
        base = RUN_BASE.get("done")
        try:
            done_now = int(ov.get('erledigt', 0))
        except (TypeError, ValueError):
            done_now = 0
        remaining = RUN_TARGET if base is None else max(0, RUN_TARGET - (done_now - base))
        
        lanes = {}
        if is_active:
            lanes['worker-1'] = {'phase': 'RUNNING', 'task': {'task_id': current_task}}
            
        D = {
            'kind': 'MAC_ADAPTER',
            'live_muse': 'UNPROVEN',
            'workspace': str(ROOT),
            'demo_directory': str(ROOT),
            'independent_acceptance': 'PENDING',
            'loaded_build': LOADED_BUILD,
            'source_build': build_identity(),
            'helper_active': helper_active,
            'helper_exit': CHILD.poll() if CHILD is not None else None,
            'session': {'count': count, 'mode': mode,
                        'target': RUN_TARGET, 'remaining': remaining},
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
        try:
            if os.environ.get("COURIER_CANNON_PROFILE") == "yolo":
                _p = os.path.join(str(ROOT), "scripts")
                if _p not in sys.path: sys.path.insert(0, _p)
                import cannon_yolo
                _lv = cannon_yolo.live_payload()
                if _lv: D["live"] = _lv
        except Exception: pass
        return D

def action(body):
    global CHILD, JOB
    action_type = body.get('action')
    if action_type not in {'START', 'RESUME', 'PAUSE', 'STOP_AFTER_CURRENT'}:
        raise ValueError('Unknown Cannon action')
        
    with LOCK:
        active = CHILD is not None and CHILD.poll() is None
        if action_type in {'PAUSE', 'STOP_AFTER_CURRENT'}:
            if action_type == 'PAUSE':
                subprocess.check_call([sys.executable, str(MAC_ADAPTER), "pause"])
            else:
                subprocess.check_call([sys.executable, str(MAC_ADAPTER), "stop"])
            return {'ok': True}
            
        if action_type == 'START':
            count = body.get('count', 5)
            mode = body.get('mode', 'BEGRENZT')
            
            if JOB: JOB.close(); JOB = None
            if CHILD is not None and CHILD.stdin: CHILD.stdin.close()
            art = "unendlich" if mode == "UNENDLICH" else "begrenzt"
            limit = str(count) if art == "begrenzt" else "1000000"

            # Normal product path: no executor choice here. REAL_MUSE tasks
            # already in the queue run through the proven motor path; the
            # local deterministic entry stays available separately via the
            # mac_adapter --local-fake CLI flag used by tests.
            command = [sys.executable, str(MAC_ADAPTER), "dauerlauf", "--art", art, "--limit", limit]
            CHILD, JOB, _ = launch_gated(command, str(ROOT), dict(os.environ), stderr=subprocess.PIPE)
            RUN_BASE["done"] = _current_done()
            
            def bounded_errors(child):
                for chunk in iter(lambda: child.stderr.read(1024), b''):
                    pass
            threading.Thread(target=bounded_errors, args=(CHILD,), daemon=True).start()
            
            return {'ok': True}
            
        if action_type == 'RESUME':
            subprocess.check_call([sys.executable, str(MAC_ADAPTER), "resume"])
            if not active:
                # if not active, we need to spawn it again to continue supervision
                command = [sys.executable, str(MAC_ADAPTER), "dauerlauf", "--art", "begrenzt", "--limit", "1000000"]
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
