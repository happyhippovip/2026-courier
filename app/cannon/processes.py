import os
import signal
import subprocess

class WindowsJob:
    def __init__(self, process):
        self.process = process
        self.pid = process.pid

    def close(self):
        try:
            if os.name == 'nt':
                try:
                    import psutil
                    p = psutil.Process(self.pid)
                    for c in p.children(recursive=True):
                        try: c.kill()
                        except Exception: pass
                    p.kill()
                except Exception:
                    self.process.kill()
            else:
                if hasattr(os, 'killpg') and hasattr(signal, 'SIGKILL'):
                    os.killpg(self.pid, signal.SIGKILL)
                else:
                    self.process.kill()
        except Exception:
            pass

def process_identity(process, command):
    return {'pid': process.pid, 'parent_pid': os.getpid(), 'creation_filetime': None,
            'executable': command[0], 'command': command}

def launch_gated(command, cwd, env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
    kwargs = {}
    if os.name != 'nt':
        kwargs['start_new_session'] = True
    else:
        if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                             stdout=stdout, stderr=stderr, **kwargs)
    try:
        job = WindowsJob(child)
        return child, job, process_identity(child, command)
    except BaseException:
        try:
            if os.name == 'nt':
                child.kill()
            else:
                if hasattr(os, 'killpg') and hasattr(signal, 'SIGKILL'):
                    os.killpg(child.pid, signal.SIGKILL)
                else:
                    child.kill()
        except Exception:
            pass
        try:
            child.wait(timeout=5)
        except Exception:
            pass
        if child.stdin:
            try: child.stdin.close()
            except Exception: pass
        raise
