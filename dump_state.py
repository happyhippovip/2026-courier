import sqlite3
import json

db_path = r'C:\Users\lol\2026-workspace\courier\chief_control_plane.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

tables_to_check = ['dispatch_queue', 'tasks', 'resource_locks', 'durable_continuation_state', 'crash_proof_state', 'handoffs', 'checkpoints', 'fenced_resource_locks']

for t in tables_to_check:
    print(f'\n--- {t} ---')
    c.execute(f"PRAGMA table_info({t});")
    print("Schema:", c.fetchall())
    c.execute(f"SELECT * FROM {t};")
    print("Rows:", c.fetchall())
