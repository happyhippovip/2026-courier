#!/usr/bin/env python3
import json
import os
import argparse
from collections import Counter
from datetime import datetime

LEDGER_PATH = "ops/ai/wall_ledger/ledger.jsonl"

def load_ledger():
    if not os.path.exists(LEDGER_PATH):
        print(f"Error: {LEDGER_PATH} not found.")
        return []
    entries = []
    with open(LEDGER_PATH, 'r') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception as e:
                print(f"Error parsing line {i+1}: {e}")
    return entries

def save_ledger(entries, path=LEDGER_PATH):
    with open(path, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')
    print(f"Saved {len(entries)} entries to {path}")

def cmd_audit(args):
    entries = load_ledger()
    status_counts = Counter()
    missing_evidence = []
    
    for data in entries:
        status_counts[data.get("STATUS", "UNKNOWN")] += 1
        evidence_path = data.get("EVIDENCE_PATH")
        if evidence_path and not os.path.exists(evidence_path):
            missing_evidence.append(data.get("TASK_ID", "UNKNOWN"))
            
    print(f"--- Ledger Audit ({len(entries)} total entries) ---")
    print("Status Breakdown:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
        
    print(f"\nMissing Evidence Files: {len(missing_evidence)}")
    if missing_evidence:
        print("First 10 missing IDs:")
        for t in missing_evidence[:10]:
            print(f"  - {t}")

def cmd_clean(args):
    entries = load_ledger()
    valid_entries = []
    removed_count = 0
    
    for data in entries:
        evidence_path = data.get("EVIDENCE_PATH")
        if evidence_path and not os.path.exists(evidence_path):
            removed_count += 1
            continue
        valid_entries.append(data)
        
    if removed_count > 0:
        backup = f"{LEDGER_PATH}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        os.rename(LEDGER_PATH, backup)
        save_ledger(valid_entries)
        print(f"Cleaned {removed_count} invalid entries. Backup saved to {backup}")
    else:
        print("Ledger is already clean.")

def main():
    parser = argparse.ArgumentParser(description="Ledger Toolkit")
    subparsers = parser.add_subparsers(dest="command")
    
    audit_parser = subparsers.add_parser("audit", help="Audit the ledger for missing files and show stats")
    clean_parser = subparsers.add_parser("clean", help="Remove ledger entries with missing evidence files")
    
    args = parser.parse_args()
    if args.command == "audit":
        cmd_audit(args)
    elif args.command == "clean":
        cmd_clean(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
