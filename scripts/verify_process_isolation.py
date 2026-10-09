import os
import psutil
import socket
import sys

def check_process_isolation(port=8080):
    errors = []
    
    # 1. Port Ownership Check
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    if result == 0:
        errors.append(f"Port {port} is already in use by a foreign process!")
    sock.close()
    
    # 2. PGID isolation (Mock for Windows, useful for Mac)
    if hasattr(os, 'getsid'):
        sid = os.getsid(os.getpid())
        # We ensure we are in a clean session/group
        if not sid:
            errors.append("Invalid session ID.")
            
    # 3. Process limit / Heavy job admission
    current_heavy_jobs = 0
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            cmd = p.info['cmdline']
            if cmd and 'server.app' in cmd:
                current_heavy_jobs += 1
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            errors.append("A process could not be read; isolation not verified.")
            
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
    check_process_isolation()
