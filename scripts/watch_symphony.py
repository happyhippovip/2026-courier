import json, time, os, sys

def watch():
    print("\033[2J\033[H") # Clear screen
    print("=== COURIER SYMPHONY LIVE STATUS ===")
    
    try:
        with open("events/founder-mode/goals.json") as f:
            goals = json.load(f)
        if goals:
            print(f"\nACTIVE GOAL: {goals[0].get('goal')}")
            print(f"GOAL STATUS: {goals[0].get('status')}")
    except Exception:
        pass

    try:
        with open("events/mission-queue/queue.json") as f:
            q = json.load(f)
        print("\n--- AUTONOMOUS MISSIONS ---")
        for i, m in enumerate(q.get("missions", [])):
            action = m.get("task", {}).get("action", m.get("normalized_task"))
            print(f"Task {i+1}: {action}  --->  [{m.get('status')}]")
    except Exception:
        pass
    print("\nPress Ctrl+C to exit.")

if __name__ == "__main__":
    while True:
        watch()
        time.sleep(2)
