import ast
with open("out.log") as f:
    lines = f.readlines()
for line in lines:
    if line.startswith("GOALS: "):
        j = ast.literal_eval(line[7:])
        goal = j["goal"]
        plan = goal.get("workflow_plan", [])
        for t in plan:
            print(f"Plan Task {t['task_id']} status: {t['status']}, blocker: {t.get('blocker')}")
