import sqlite3
import json

db_path = r'C:\Users\lol\2026-workspace\courier\chief_control_plane.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("--- durable_continuation_state ---")
for row in c.execute("SELECT * FROM durable_continuation_state").fetchall():
    print(row)

print("\n--- tasks ---")
for row in c.execute("SELECT * FROM tasks WHERE status != 'COMPLETED'").fetchall():
    print(row)

print("\n--- resource_locks ---")
for row in c.execute("SELECT * FROM resource_locks WHERE status = 'ACQUIRED'").fetchall():
    print(row)

print("\n--- dispatch_queue ---")
for row in c.execute("SELECT * FROM dispatch_queue WHERE status != 'COMPLETED' AND status != 'DELIVERED'").fetchall():
    print(row)
