import os
import sys
import sqlite3
import json
import time
import subprocess
import ctypes

print("=== SYSTEM RESOURCE FORENSICS ===")
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

stat = MEMORYSTATUSEX()
stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))

total_gb = stat.ullTotalPhys / (1024**3)
avail_gb = stat.ullAvailPhys / (1024**3)
print(f"Memory Load: {stat.dwMemoryLoad}%")
print(f"RAM Total: {total_gb:.2f} GB, Available: {avail_gb:.2f} GB")
print("Thermal Sensors: THERMAL_CAUSE_UNPROVEN (Standard Windows API does not expose ACPI thermal sensors to userland)")

print("\n=== PROCESS AUDIT VIA TASKLIST ===")
try:
    p = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5)
    node_count = 0
    python_count = 0
    total_procs = 0
    for line in p.stdout.splitlines():
        total_procs += 1
        low = line.lower()
        if "node.exe" in low:
            node_count += 1
        elif "python.exe" in low:
            python_count += 1
    print(f"Total Running Windows Processes: {total_procs}")
    print(f"node.exe instances: {node_count}")
    print(f"python.exe instances: {python_count}")
except Exception as e:
    print(f"Tasklist error: {e}")

print("\n=== SQLITE DATABASE AUDIT ===")
db_path = r"C:\Users\lol\2026-workspace\courier\chief_control_plane.db"
if os.path.exists(db_path):
    print(f"DB Size: {os.path.getsize(db_path)} bytes")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM tasks")
    print(f"Total tasks in tasks table: {cur.fetchone()[0]}")
    cur.execute("SELECT task_id, status, blocker FROM tasks WHERE status IN ('RUNNING', 'CLAIMED', 'PENDING')")
    open_tasks = cur.fetchall()
    print(f"Open/Running tasks ({len(open_tasks)}): {open_tasks}")
    cur.execute("SELECT count(*) FROM checkpoints")
    print(f"Total checkpoints: {cur.fetchone()[0]}")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables in DB: {tables}")
    cur.execute("SELECT task_id, status, blocker, updated_at FROM tasks ORDER BY updated_at DESC LIMIT 5")
    recent = cur.fetchall()
    print("5 Most Recent Tasks:")
    for r in recent:
        print(" ", r)
    conn.close()
else:
    print("DB does not exist!")

print("\n=== TASK LOGS AUDIT ===")
task_log_dir = r"C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\.system_generated\tasks"
if os.path.exists(task_log_dir):
    logs = [os.path.join(task_log_dir, f) for f in os.listdir(task_log_dir) if f.endswith(".log")]
    print(f"Found {len(logs)} task log files. Inspecting newest 4:")
    logs.sort(key=os.path.getmtime, reverse=True)
    for log_path in logs[:4]:
        name = os.path.basename(log_path)
        size = os.path.getsize(log_path)
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = "".join(lines[-4:]) if lines else "EMPTY"
        print(f"Log: {name} (size {size}b):\n{tail.strip()}\n")
