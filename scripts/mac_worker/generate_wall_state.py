import csv
import os

wall_dir = os.path.expanduser("~/Downloads/courier_work/wall")
state_file = os.path.join(wall_dir, "state.tsv")

SESSIONS = [
    ("MUSE", 1, 64, "muse", "muse --yolo"),
    ("CLI", 1, 9, "cli", "HOME=/Users/user/.gemini_alt agy"),
]

def generate_state():
    with open(state_file, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["slot_id", "wid", "worker_type", "account_provider", "task_id", "scope", "state", "claim_created_at", "pid", "pty", "proof_ref", "next_action", "blocker"])
        
        for prefix, start, end, worker_type, cmd in SESSIONS:
            for i in range(start, end + 1):
                slot_id = f"{prefix}-{i:02d}"
                claim_dir = os.path.join(wall_dir, "claims", slot_id)
                has_claim = "YES" if os.path.exists(claim_dir) else "NO"
                writer.writerow([slot_id, "", worker_type, "default", "", "", "IDLE", "", "", "", "", "start", ""])

    print(f"Generated {state_file} with 73 mapped sessions.")

if __name__ == "__main__":
    generate_state()
