import sqlite3
import json

db_path = r'C:\Users\lol\2026-workspace\courier\chief_control_plane.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Update dispatch_queue to mark any STAGED/DISPATCHED as COMPLETED or DELIVERED to clear active items.
c.execute("UPDATE dispatch_queue SET status = 'COMPLETED' WHERE status IN ('STAGED', 'DISPATCHED')")
print(f"dispatch_queue marked completed: {c.rowcount}")

# 2. Check and remove Step 9 / 10 if present in dispatch_queue (not needed if we clear them all, but just in case)
c.execute("DELETE FROM dispatch_queue WHERE prompt_text LIKE '%Step 9%' OR envelope_json LIKE '%Step 9%' OR prompt_text LIKE '%Step 10%' OR envelope_json LIKE '%Step 10%'")
print(f"False Step 9/10 removed from dispatch_queue: {c.rowcount}")

conn.commit()
print("Done.")
