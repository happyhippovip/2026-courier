import json
import os

p = 'tmp_cannon_transfer/app/cannon/web.py'
with open(p, 'r') as f:
    web = f.read()

# We will completely replace web.py to be a bridge to mac_adapter.
new_web = """import os
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
        is_active = mac.get('state') in ('RUNNING', 'STOP_AFTER_CURRENT')
        helper_active = CHILD is not None and CHILD.poll() is None
        
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
            
            subprocess.check_call([sys.executable, str(MAC_ADAPTER), "seed", "--n", str(count)])
            
            art = "unendlich" if mode == "UNENDLICH" else "begrenzt"
            limit = str(count) if art == "begrenzt" else "1000000"
            
            command = [sys.executable, str(MAC_ADAPTER), "dauerlauf", "--art", art, "--limit", limit]
            CHILD, JOB, _ = launch_gated(command, str(ROOT), dict(os.environ), stderr=subprocess.PIPE)
            
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
"""
with open(p, 'w') as f:
    f.write(new_web)
print("Rewrote web.py")
