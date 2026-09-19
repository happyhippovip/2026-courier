import os
import sys

def patch_controller():
    p = 'tmp_cannon_transfer/app/cannon/controller.py'
    with open(p, 'r') as f:
        data = f.read()
    
    new_resource = """def resource_state():
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent >= 90 or mem.available < 512 * 1024**2: return 'RED'
        if mem.percent >= 75 or mem.available < 1024**3: return 'YELLOW'
        return 'GREEN'
    except Exception:
        return 'GREEN'
"""
    # Replace the old resource_state function
    import re
    data = re.sub(r'def resource_state\(\):.*?return \'GREEN\'\n', new_resource, data, flags=re.DOTALL)
    with open(p, 'w') as f:
        f.write(data)

def patch_web():
    p = 'tmp_cannon_transfer/app/cannon/web.py'
    with open(p, 'r') as f:
        data = f.read()

    data = data.replace("python = ROOT / '.venv/Scripts/python.exe'", "")
    data = data.replace("if not python.is_file(): raise ValueError('New-workspace test Python unavailable')", "")
    data = data.replace("env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'USERPROFILE'}}", "env = dict(os.environ)")
    data = data.replace("env.update(PYTHONPATH=os.pathsep.join([str(ROOT / 'app'), str(ROOT / '.venv/Lib/site-packages')]), PYTHONDONTWRITEBYTECODE='1', CANNON_DEMO_DIR=str(directory))", "env.update(PYTHONPATH=str(ROOT / 'app'), PYTHONDONTWRITEBYTECODE='1', CANNON_DEMO_DIR=str(directory))")
    data = data.replace("interpreter = Path(getattr(sys, '_base_executable', sys.executable)).with_name('python.exe')", "interpreter = sys.executable")
    
    with open(p, 'w') as f:
        f.write(data)

def patch_processes():
    p = 'tmp_cannon_transfer/app/cannon/processes.py'
    with open(p, 'r') as f:
        data = f.read()
    
    new_code = """import os
import signal
import subprocess

class WindowsJob:
    def __init__(self, process):
        self.pid = process.pid

    def close(self):
        try:
            os.killpg(self.pid, signal.SIGKILL)
        except Exception:
            pass

def process_identity(process, command):
    return {'pid': process.pid, 'parent_pid': os.getpid(), 'creation_filetime': None,
            'executable': command[0], 'command': command}

def launch_gated(command, cwd, env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                             stdout=stdout, stderr=stderr, start_new_session=True)
    try:
        job = WindowsJob(child)
        return child, job, process_identity(child, command)
    except BaseException:
        try: os.killpg(child.pid, signal.SIGKILL)
        except OSError: pass
        child.wait(timeout=5)
        if child.stdin: child.stdin.close()
        raise
"""
    with open(p, 'w') as f:
        f.write(new_code)

patch_controller()
patch_web()
patch_processes()
print("Patched.")
