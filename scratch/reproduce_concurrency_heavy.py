import sqlite3
import time
import subprocess
import os

# Create DB with 1 task
if os.path.exists(".courier_state/motor.db"):
    os.remove(".courier_state/motor.db")

from pathlib import Path
import sys
sys.path.insert(0, str(Path("build/courier_ecosystem_v1/motor").resolve()))
from supervisor_standalone import init_env

conn = init_env()
conn.execute("INSERT INTO tasks (task_id, instruction, status, priority) VALUES ('CONCURRENCY-1', 'sleep 0.5', 'PENDING', 10)")
conn.commit()

# Start two supervisors concurrently
sup1 = subprocess.Popen(["python3", "build/courier_ecosystem_v1/motor/supervisor_standalone.py", "run"])
sup2 = subprocess.Popen(["python3", "build/courier_ecosystem_v1/motor/supervisor_standalone.py", "run"])

time.sleep(3)
sup1.terminate()
sup2.terminate()

# Check how many attempts were made
c = conn.cursor()
c.execute("SELECT attempt_id, pid FROM attempts WHERE task_id='CONCURRENCY-1'")
attempts = c.fetchall()
print(f"Attempts: {len(attempts)}")
for att in attempts:
    print(f" - Attempt {att[0]} by PID {att[1]}")
if len(attempts) > 1:
    print("CONCURRENCY_DEFECT_REPRODUCED")
else:
    print("NO_DEFECT")

# Launch 10 supervisors
sups = []
for _ in range(10):
    sups.append(subprocess.Popen(["python3", "build/courier_ecosystem_v1/motor/supervisor_standalone.py", "run"]))

time.sleep(3)
for s in sups:
    s.terminate()

c = conn.cursor()
c.execute("SELECT attempt_id, pid FROM attempts WHERE task_id='CONCURRENCY-1'")
attempts = c.fetchall()
print(f"Attempts: {len(attempts)}")
