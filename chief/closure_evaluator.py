"""
closure_evaluator.py - Stdin/Stdout CLI Runner for Two-Level Closure Gate
Invoked by Studio server or external agents to evaluate task closure via JSON stdin.
"""

import sys
import json
from courier.chief.closure_gate import TwoLevelClosureGate

def main():
    try:
        raw_in = sys.stdin.read()
        payload = json.loads(raw_in) if raw_in.strip() else {}
        task_id = payload.get("task_id")
        if not task_id:
            print(json.dumps({"success": False, "error": "Missing task_id"}))
            sys.exit(1)

        gate = TwoLevelClosureGate()
        report = gate.evaluate_task_closure(
            task_id=task_id,
            execution_evidence=payload.get("execution_evidence"),
            remote_peer_synced=bool(payload.get("remote_peer_synced", False)),
            requires_human_gate=bool(payload.get("requires_human_gate", False)),
            spend_eur=float(payload.get("spend_eur", 0.0))
        )
        print(json.dumps(report))
        sys.exit(0 if report.get("success") else 1)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(2)

if __name__ == "__main__":
    main()
