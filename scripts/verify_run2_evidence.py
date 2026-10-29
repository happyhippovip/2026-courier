import os
import sqlite3
import sys
import json

def verify_run2_evidence(evidence_dir="artifacts/run2"):
    log(f"Verifying RUN_2 Evidence in {evidence_dir}")
    
    server_log = os.path.join(evidence_dir, "server_run2.log")
    worker_log = os.path.join(evidence_dir, "worker_run2.log")
    ledger_db = os.path.join(evidence_dir, "ledger_run2.db")
    
    errors = []
    
    if not os.path.exists(ledger_db):
        errors.append("ledger_run2.db is missing")
    else:
        conn = sqlite3.connect(ledger_db)
        cursor = conn.cursor()
        
        # 1. A is still RECONCILED (GQ23)
        cursor.execute("SELECT status FROM tasks WHERE task_id='A'")
        res = cursor.fetchone()
        if not res or res[0] != 'RECONCILED':
            errors.append(f"Task A is not RECONCILED after RUN_2. Current: {res[0] if res else 'MISSING'}")
            
        # 2. B reached RECONCILED
        cursor.execute("SELECT status FROM tasks WHERE task_id='B'")
        res = cursor.fetchone()
        if not res or res[0] != 'RECONCILED':
            errors.append(f"Task B is not RECONCILED. Current: {res[0] if res else 'MISSING'}")
    
    # 3. Check for Task A re-execution. A missing log is not evidence of no replay.
    if not os.path.exists(server_log):
        errors.append("server_run2.log is missing")
    else:
        with open(server_log, "r") as f:
            content = f.read()
            if "Claimed task A" in content or "Result for task A" in content:
                errors.append("Task A was incorrectly dispatched again in RUN_2!")
    
    if not errors:
        print("RUN_2 EVIDENCE VALID: A_SURVIVED, B_RECONCILED, NO_REPLAYS")
        sys.exit(0)
    else:
        print("RUN_2 EVIDENCE FAILED:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

def log(msg):
    print(f"[Evidence Checker] {msg}")

if __name__ == "__main__":
    verify_run2_evidence()
