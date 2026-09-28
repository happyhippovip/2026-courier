import subprocess, time, sys

try:
    p = subprocess.Popen(["powershell", "-Command", "Start-Sleep -Seconds 10"], stdout=subprocess.PIPE)
    p.communicate(timeout=1)
except subprocess.TimeoutExpired:
    print("Timeout")
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
