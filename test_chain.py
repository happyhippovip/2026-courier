import requests, json, time

print("Setting up goal...")
# Goal with two steps A and B. B depends on A.
goal = {
    "goal_text": "harmless chain",
    "terminal": True
}
res = requests.post("http://localhost:8080/goals/create", json=goal)
# wait, how to create a goal with a specific workflow plan?
