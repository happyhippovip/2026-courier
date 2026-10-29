import json
import os
import psutil
import socket
import sys

def session_boundary_verified(record_path) -> bool:
    """True only when a session record reads back to a different live session."""
    if not record_path or not hasattr(os, "getsid"):
        return False
    if not os.path.isfile(record_path):
        return False
    try:
        with open(record_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return False
    if not isinstance(record, dict):
        return False
    pid = record.get("pid")
    recorded_sid = record.get("sid")
    if type(pid) is not int or type(recorded_sid) is not int or pid <= 0 or recorded_sid <= 0:
        return False
    try:
        live_sid = os.getsid(pid)
        own_sid = os.getsid(os.getpid())
    except OSError:
        return False
    if live_sid != recorded_sid or live_sid == own_sid or recorded_sid != pid:
        return False
    try:
        process = psutil.Process(pid)
        if process.status() == psutil.STATUS_ZOMBIE or not process.is_running():
            return False
    except psutil.Error:
        return False
    return True

def check_process_isolation(port=8080, session_record=None):
    errors = []
    
    # 1. Port Ownership Check
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    if result == 0:
        errors.append(f"Port {port} is already in use by a foreign process!")
    sock.close()
    
    # 2. A nonzero getsid of this process is not a session boundary.
    if not session_boundary_verified(session_record):
        errors.append("No session boundary read back.")
            
    # 3. Process limit / Heavy job admission
    current_heavy_jobs = 0
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            cmd = p.info['cmdline']
            if cmd and 'server.app' in cmd:
                current_heavy_jobs += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    if current_heavy_jobs > 0:
        errors.append("Foreign server.app process detected running on this host.")

    if not errors:
        print("PROCESS ISOLATION VALID")
        sys.exit(0)
    else:
        print("PROCESS ISOLATION FAILED:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

if __name__ == "__main__":
    record = sys.argv[1] if len(sys.argv) > 1 else None
    check_process_isolation(session_record=record)
