import json

with open("events/founder-mode/goals.json", "r") as f:
    goals = json.load(f)

for g in goals:
    if g.get("status") == "PENDING" and g.get("goal_id") != "c8016212-cd9b-4b3f-95af-9c096cd7f319":
        g["status"] = "SATISFIED"

with open("events/founder-mode/goals.json", "w") as f:
    json.dump(goals, f, indent=2)
