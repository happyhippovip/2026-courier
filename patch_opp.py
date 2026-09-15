import json
with open("events/opportunity-queue/TASK_FOUNDATION_1789426699.json", "r") as f:
    opp = json.load(f)
opp["allowed_scope"] = ["scripts"]
with open("events/opportunity-queue/TASK_FOUNDATION_1789426699.json", "w") as f:
    json.dump(opp, f, indent=2)
