#!/usr/bin/env python3
import json
import os
import sys

LEDGER_PATH = "ops/ai/wall_ledger/ledger.jsonl"
COURIER_DIR = os.path.dirname(os.path.abspath(__file__))

def check_integrity():
    if not os.path.exists(LEDGER_PATH):
        print(f"Error: {LEDGER_PATH} not found.")
        sys.exit(1)

    print("=== Cryptographic Ledger Integrity Check ===")
    total = 0
    mismatches = 0
    missing_files = 0
    dirs_found = 0
    valid = 0

    with open(LEDGER_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            data = json.loads(line)
            task_id = data.get("TASK_ID")
            ledger_fp = data.get("FINGERPRINT")
            ev_path = data.get("EVIDENCE_PATH")

            if not ev_path:
                missing_files += 1
                continue
                
            full_path = os.path.join(COURIER_DIR, ev_path)
            if not os.path.exists(full_path):
                missing_files += 1
                continue
                
            if os.path.isdir(full_path):
                dirs_found += 1
                continue

            file_fp = None
            legacy_fp = None
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as ef:
                for eline in ef:
                    if "DO_NOT_REPEAT_FINGERPRINT=" in eline:
                        file_fp = eline.split("DO_NOT_REPEAT_FINGERPRINT=")[1].strip()
                    elif "DO_NOT_REPEAT:" in eline:
                        legacy_fp = eline.split("DO_NOT_REPEAT:")[1].strip()
            
            final_fp = file_fp if file_fp else legacy_fp

            if not final_fp:
                mismatches += 1
            elif final_fp != ledger_fp:
                mismatches += 1
            else:
                valid += 1

    print("\n--- Integrity Report ---")
    print(f"Total Ledger Entries: {total}")
    print(f"Valid and Matched:    {valid}")
    print(f"Missing Evidence:     {missing_files}")
    print(f"Evidence is a Dir:    {dirs_found}")
    print(f"Fingerprint Errors:   {mismatches}")

    if mismatches == 0 and missing_files == 0 and dirs_found == 0:
        print("\n✅ Ledger is 100% cryptographically intact.")
    else:
        print("\n❌ Ledger integrity violations detected!")
        if missing_files > 0:
            print("   -> Run './ledger_toolkit.py clean' to remove entries with missing evidence.")
        if mismatches > 0:
            print("   -> Run './ledger_repair.py' to heal fingerprint mismatches.")

if __name__ == "__main__":
    check_integrity()
