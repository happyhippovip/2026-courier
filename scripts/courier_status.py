#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Anchor to the repository tree holding this script so the tool reads the
# real central state regardless of the caller's working directory.
REPO_ROOT = Path(__file__).resolve().parent.parent


def main(root=None):
    state_file = (Path(root) if root is not None else REPO_ROOT) / "server" / "state" / "central_state.json"
    if not state_file.exists():
        print("Courier Symphony: No ledger found.")
        return 0

    try:
        with open(state_file, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"Courier Symphony: state unreadable: {exc}")
        return 1

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
    return 0

if __name__ == "__main__":
    sys.exit(main())
