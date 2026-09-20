import subprocess, sys, time, os, urllib.request

env = os.environ.copy()
env["PORT"] = "8081"
print("Starting server/app.py")
proc = subprocess.Popen([sys.executable, "server/app.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)

if proc.poll() is not None:
    print("Process exited with code", proc.returncode)
    print("Stdout:", proc.stdout.read().decode())
    print("Stderr:", proc.stderr.read().decode())
else:
    print("Process is running.")
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8081/health")
        print("Health:", r.read().decode())
    except Exception as e:
        print("Error hitting health:", e)
        print("Killing proc...")
    proc.terminate()
    proc.wait()
    print("Stdout:", proc.stdout.read().decode())
    print("Stderr:", proc.stderr.read().decode())
