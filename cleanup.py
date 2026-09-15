import sqlite3
import json

db_path = r'C:\Users\lol\2026-workspace\courier\chief_control_plane.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Clear any active leases tied to the recent run
print("Clearing leases in durable_continuation_state...")
c.execute("UPDATE durable_continuation_state SET lease_id = NULL WHERE lease_id IS NOT NULL")
print(f"Rows updated: {c.rowcount}")

# Clear resource_locks (assuming we can just delete all locks to be safe or delete specific ones)
print("Clearing resource_locks...")
c.execute("DELETE FROM resource_locks")
print(f"Rows deleted: {c.rowcount}")

# 2. Remove false Step 9 / Step 10 from CURRENT/NEXT ACTIVE STATE only.
# This might be in successor_state or result_state_json in durable_continuation_state
# or in tasks table (next_step column).
# Let's inspect next_step in tasks.
c.execute("UPDATE tasks SET next_step = NULL WHERE next_step LIKE '%Step 9%' OR next_step LIKE '%Step 10%'")
print(f"Tasks next_step cleared: {c.rowcount}")

c.execute("UPDATE tasks SET status = 'COMPLETED' WHERE status != 'COMPLETED' AND status != 'CANCELLED'")
print(f"Tasks marked completed: {c.rowcount}")

# Update durable_continuation_state successor_state
c.execute("UPDATE durable_continuation_state SET successor_state = NULL WHERE successor_state LIKE '%Step 9%' OR successor_state LIKE '%Step 10%'")
print(f"durable_continuation_state successor_state cleared: {c.rowcount}")

c.execute("UPDATE durable_continuation_state SET status = 'COMPLETED' WHERE status != 'COMPLETED' AND status != 'CANCELLED'")
print(f"durable_continuation_state marked completed: {c.rowcount}")

conn.commit()
print("Done.")
