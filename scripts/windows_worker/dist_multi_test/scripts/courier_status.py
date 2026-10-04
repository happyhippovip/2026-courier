#!/usr/bin/env python3
import json
from pathlib import Path

def main():
    state_file = Path("server/state/central_state.json")
    if not state_file.exists():
        print("Courier Symphony: No ledger found.")
        return
        
    with open(state_file, "r") as f:
        state = json.load(f)
        
    unassigned = 0
    goals = state.get("goals", {})
    for g in goals.values():
        if g.get("status") == "ACTIVE":
            for step in g.get("workflow_plan", []):
                if step.get("status") == "UNASSIGNED":
                    unassigned += 1
                    
    health = "GREEN" if unassigned == 0 else "YELLOW"
    print(f"=== COURIER STATUS ===")
    print(f"Health: {health}")
    print(f"Unassigned P0 Tasks: {unassigned}")
    print(f"Active Goals: {len([g for g in goals.values() if g.get('status') == 'ACTIVE'])}")

if __name__ == "__main__":
    main()
