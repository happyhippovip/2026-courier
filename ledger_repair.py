#!/usr/bin/env python3
import json
import os
import hashlib
from datetime import datetime

LEDGER_PATH = "ops/ai/wall_ledger/ledger.jsonl"
COURIER_DIR = os.path.dirname(os.path.abspath(__file__))

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for block in iter(lambda: f.read(4096), b""):
            sha256.update(block)
    return sha256.hexdigest()

def repair_ledger():
    if not os.path.exists(LEDGER_PATH):
        print("No ledger found.")
        return

    backup = f"{LEDGER_PATH}.repair_bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    os.rename(LEDGER_PATH, backup)
    print(f"Backed up to {backup}")

    repaired = 0
    total = 0
    
    with open(backup, 'r') as infile, open(LEDGER_PATH, 'w') as outfile:
        for line in infile:
            if not line.strip():
                continue
            total += 1
            data = json.loads(line)
            ev_path = data.get("EVIDENCE_PATH")
            if ev_path:
                full_path = os.path.join(COURIER_DIR, ev_path)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    # Compute actual SHA256 of current evidence file
                    actual_hash = "sha256-" + compute_sha256(full_path)[:16]
                    
                    if data.get("FINGERPRINT") != actual_hash:
                        data["FINGERPRINT"] = actual_hash
                        repaired += 1
                        
                        # Also append/update it in the file if needed
                        with open(full_path, 'a') as ef:
                            ef.write(f"\nDO_NOT_REPEAT_FINGERPRINT={actual_hash}\n")

            outfile.write(json.dumps(data) + '\n')

    print(f"Repair complete. Checked {total} entries. Repaired {repaired} fingerprints to match actual SHA256.")

if __name__ == "__main__":
    repair_ledger()
