import os
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
