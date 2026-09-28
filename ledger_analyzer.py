import json
import os
from collections import Counter

LEDGER_PATH = "ops/ai/wall_ledger/ledger.jsonl"

def analyze_ledger():
    if not os.path.exists(LEDGER_PATH):
        print(f"Error: {LEDGER_PATH} not found.")
        return

    status_counts = Counter()
    missing_evidence = []
    total_lines = 0

    print("Analyzing Ledger...")
    with open(LEDGER_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                data = json.loads(line)
                status = data.get("STATUS", "UNKNOWN")
                status_counts[status] += 1
                
                evidence_path = data.get("EVIDENCE_PATH")
                if evidence_path:
                    if not os.path.exists(evidence_path):
                        missing_evidence.append(data.get("TASK_ID", "UNKNOWN"))
            except Exception as e:
                print(f"Error parsing line {total_lines}: {e}")

    print("-" * 30)
    print(f"Total Entries: {total_lines}")
    print("\nStatus Breakdown:")
    for status, count in status_counts.items():
        print(f" - {status}: {count}")

    print(f"\nMissing Evidence Files: {len(missing_evidence)}")
    if missing_evidence:
        print("First 10 missing:")
        for t in missing_evidence[:10]:
            print(f" - {t}")

if __name__ == "__main__":
    analyze_ledger()
