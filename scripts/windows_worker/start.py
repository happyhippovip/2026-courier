import subprocess, sys, os
if not os.path.exists('logs'): os.makedirs('logs')
with open(os.path.join('logs', 'worker.log'), 'a') as f:
    subprocess.Popen([sys.executable, '-u', 'daemon.py'], stdout=f, stderr=f, creationflags=0x08000008)
