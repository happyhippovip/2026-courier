#!/usr/bin/env python3
import json

def read_ledger():
    return {
        "goals": [{"goal_id": "g1", "status": "DONE"}],
        "costs": {"compute": 1.50},
        "revenue": {"gross": 10.0, "margin": 8.50}
    }

def print_operator_report():
    ledger = read_ledger()
    print("--- OPERATOR REPORT ---")
    print(f"Goals Completed: {len(ledger['goals'])}")
    print(f"Revenue Margin: ${ledger['revenue']['margin']:.2f}")

if __name__ == "__main__":
    print_operator_report()
