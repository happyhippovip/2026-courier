import csv
import os

wall_dir = os.path.expanduser("~/Downloads/courier_work/wall")
state_file = os.path.join(wall_dir, "state.tsv")

SESSIONS = [
    ("M", 1, 10, "Mac Courier Worker", "courier_continue.py --run"),
    ("W", 1, 10, "Windows Opus Worker", "Invoke-CourierWorker.ps1"),
    ("V", 1, 5, "Independent Verifier", "courier_verifier.py --watch"),
    ("D", 1, 5, "Watchdog Daemons", "run_snitch_watchdog.py"),
    ("T", 1, 34, "Tests & Operations", "pytest"),
]

with open(state_file, "w", newline="") as f:
    writer = csv.writer(f, delimiter="\t")
    writer.writerow(["SESSION_ID", "ROLE", "COMMAND_BINDING", "STATUS", "LAST_CLAIM"])
    
    for prefix, start, end, role, cmd in SESSIONS:
        for i in range(start, end + 1):
            session_id = f"{prefix}{str(i).zfill(2)}"
            claim_dir = os.path.join(wall_dir, "claims", session_id)
            has_claim = "YES" if os.path.exists(claim_dir) else "NO"
            writer.writerow([session_id, role, cmd, "PENDING_REBOOT", has_claim])

print(f"Generated {state_file} with 64 mapped sessions.")
