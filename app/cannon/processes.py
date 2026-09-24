import ctypes
import os
import signal
import subprocess


if os.name == 'nt':
    from ctypes import wintypes as W

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ('ReadOperationCount', ctypes.c_ulonglong),
            ('WriteOperationCount', ctypes.c_ulonglong),
            ('OtherOperationCount', ctypes.c_ulonglong),
            ('ReadTransferCount', ctypes.c_ulonglong),
            ('WriteTransferCount', ctypes.c_ulonglong),
            ('OtherTransferCount', ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', ctypes.c_longlong),
            ('PerJobUserTimeLimit', ctypes.c_longlong),
            ('LimitFlags', W.DWORD),
            ('MinimumWorkingSetSize', ctypes.c_size_t),
            ('MaximumWorkingSetSize', ctypes.c_size_t),
            ('ActiveProcessLimit', W.DWORD),
            ('Affinity', ctypes.c_size_t),
            ('PriorityClass', W.DWORD),
            ('SchedulingClass', W.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('BasicLimitInformation', _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ('IoInfo', _IO_COUNTERS),
            ('ProcessMemoryLimit', ctypes.c_size_t),
            ('JobMemoryLimit', ctypes.c_size_t),
            ('PeakProcessMemoryUsed', ctypes.c_size_t),
            ('PeakJobMemoryUsed', ctypes.c_size_t),
        ]


class WindowsJob:
    def __init__(self, process):
        self.process = process
        self.pid = process.pid
        self.job_handle = None
        if os.name == 'nt':
            try:
                k32 = ctypes.WinDLL('kernel32', use_last_error=True)
                k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, W.LPCWSTR]
                k32.CreateJobObjectW.restype = W.HANDLE
                k32.SetInformationJobObject.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD]
                k32.SetInformationJobObject.restype = W.BOOL
                k32.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
                k32.AssignProcessToJobObject.restype = W.BOOL
                job = k32.CreateJobObjectW(None, None)
                if job:
                    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000) | JOB_OBJECT_LIMIT_BREAKAWAY_OK (0x0800)
                    info.BasicLimitInformation.LimitFlags = 0x2000 | 0x0800
                    k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
                    k32.AssignProcessToJobObject(job, W.HANDLE(int(process._handle)))
                    self.job_handle = job
            except Exception:
                self.job_handle = None

    def close(self):
        try:
            if os.name == 'nt':
                if self.job_handle:
                    try:
                        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
                        k32.TerminateJobObject.argtypes = [W.HANDLE, W.UINT]
                        k32.CloseHandle.argtypes = [W.HANDLE]
                        k32.TerminateJobObject(self.job_handle, 1)
                        k32.CloseHandle(self.job_handle)
                    except Exception:
                        pass
                    self.job_handle = None
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
    creation_filetime = None
    try:
        import psutil
        creation_filetime = psutil.Process(process.pid).create_time()
    except Exception:
        import time
        creation_filetime = time.time()
    return {'pid': process.pid, 'parent_pid': os.getpid(), 'creation_filetime': creation_filetime,
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
