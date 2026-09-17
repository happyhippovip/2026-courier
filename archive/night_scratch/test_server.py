import subprocess, sys, time, os
python_exe = sys.executable
if os.path.exists("venv/bin/python"):
    python_exe = "venv/bin/python"
env = os.environ.copy()
env["PORT"] = "8081"
print(f"Starting {python_exe} server/app.py")
proc = subprocess.Popen([python_exe, "server/app.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
if proc.poll() is not None:
    print("Process exited with code", proc.returncode)
    print("Stdout:", proc.stdout.read().decode())
    print("Stderr:", proc.stderr.read().decode())
else:
    print("Process is running.")
    proc.terminate()
