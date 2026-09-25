import subprocess
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import winreg
from scripts.mutex import enforce_single_instance

def setup_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
        pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        script_path = os.path.abspath(__file__)
        cmd = f'"{pythonw_exe}" "{script_path}"'
        winreg.SetValueEx(key, 'CourierSupervisor', 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Failed to set supervisor autostart: {e}")

SERVICES = [
    ("CourierServer", "server.app", "courier_server.log"),
    ("CourierWorker", "scripts.windows_worker.daemon", "courier_worker.log"),
    ("CourierVerifier", "scripts.courier_verifier", "courier_verifier.log"),
    ("CourierWatchdog", "scripts.courier_watchdog", "courier_watchdog.log"),
]

def run_supervisor():
    setup_autostart()
    procs = {}
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    python_exe = sys.executable.replace("pythonw.exe", "python.exe")

    while True:
        for name, module, log_file in SERVICES:
            p = procs.get(name)
            if p is None or p.poll() is not None:
                log_path = os.path.join(logs_dir, log_file)
                f = open(log_path, "a")
                
                # creationflags=0x08000008 creates no window
                procs[name] = subprocess.Popen(
                    [python_exe, "-u", "-m", module],
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    cwd=base_dir,
                    creationflags=0x08000008
                )
        time.sleep(10)

if __name__ == "__main__":
    enforce_single_instance("Global\\CourierSupervisor")
    run_supervisor()
