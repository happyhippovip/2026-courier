import ctypes
import sys

_mutex_handle = None

def enforce_single_instance(mutex_name):
    global _mutex_handle
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183: # ERROR_ALREADY_EXISTS
        print(f"[{mutex_name}] Another instance is already running. Exiting.", flush=True)
        if mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)
        sys.exit(0)
    _mutex_handle = mutex
