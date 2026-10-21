import os
import sqlite3
import sys
import json

def verify_run1_evidence(evidence_dir="artifacts/run1"):
    log(f"Verifying RUN_1 Evidence in {evidence_dir}")
    
    server_log = os.path.join(evidence_dir, "server_run1.log")
    worker_log = os.path.join(evidence_dir, "worker_run1.log")
    verifier_log = os.path.join(evidence_dir, "verifier_run1.log")
    ledger_db = os.path.join(evidence_dir, "ledger_run1.db")
    
    errors = []
    
    if not os.path.exists(ledger_db):
        errors.append("ledger_run1.db is missing")
    else:
        conn = sqlite3.connect(ledger_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM tasks WHERE task_id='A'")
        res = cursor.fetchone()
        if not res or res[0] != 'RECONCILED':
            errors.append(f"Task A is not RECONCILED. Current: {res[0] if res else 'MISSING'}")
    
    # Exactly-once and no-failure are claims about the server log. A missing log is not evidence.
    if not os.path.exists(server_log):
        errors.append("server_run1.log is missing")
    else:
        with open(server_log, "r") as f:
            content = f.read()
            claims = content.count("Claimed task A")
            if claims != 1:
                errors.append(f"Task A was claimed {claims} times, expected exactly 1.")
            results = content.count("Result for task A")
            if results != 1:
                errors.append(f"Task A result submitted {results} times, expected exactly 1.")
            if "FAILED" in content or "Traceback" in content:
                errors.append("server_run1.log records a failure")
    
    if not errors:
        print("RUN_1 EVIDENCE VALID: RECONCILED, EXACTLY_ONCE, NO_FAILURES")
        sys.exit(0)
    else:
        print("RUN_1 EVIDENCE FAILED:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

def log(msg):
    print(f"[Evidence Checker] {msg}")

if __name__ == "__main__":
    verify_run1_evidence()
