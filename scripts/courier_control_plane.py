import os, json, glob, time, uuid, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_chief_commander import ChiefCommander

STATE_FILE = 'central_state.json'

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            state.setdefault("goals", {})
            state.setdefault("tasks", {})
            return state
    return {"goals": {}, "tasks": {}}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def ingest_goals(state):
    os.makedirs("goals/pending", exist_ok=True)
    for goal_file in glob.glob("goals/pending/*.json"):
        with open(goal_file, 'r') as f:
            goal = json.load(f)
        goal_id = goal.get("goal_id", f"goal-{uuid.uuid4().hex[:8]}")
        goal["status"] = "NEW"
        state["goals"][goal_id] = goal
        os.remove(goal_file)
        print(f"Ingested new goal: {goal_id}")

def determine_next_task(goal_id, state):
    goal = state["goals"][goal_id]
    goal_text = goal["goal_text"]
    
    if "workflow_plan" not in goal:
        print(f"Formulating real workflow plan for goal {goal_id} using ChiefCommander...")
        try:
            chief = ChiefCommander()
            # Suppress heavy output
            wf_id, plan = chief.formulate_workflow_plan(goal_text, idea_type="GOAL")
            
            mapped_plan = []
            for step in plan:
                target_agent = step.get("target_agent", "antigravity").lower()
                target_cap = "mac"
                if "codex" in target_agent or "windows" in target_agent:
                    target_cap = "windows"
                elif "github" in target_agent:
                    target_cap = "github"
                
                mapped_plan.append({
                    "task_id": step.get("task_id", f"task-{uuid.uuid4().hex[:8]}"),
                    "goal_id": goal_id,
                    "description": step.get("instruction", "Next step"),
                    "target_capability": target_cap,
                    "status": "QUEUED"
                })
            goal["workflow_plan"] = mapped_plan
            goal["current_step_index"] = 0
            
            # If the user specifically asks for 2 tasks for the canary, we ensure we only take the top 2 if there are many, or if the planner only gave 1, we let it be. 
            # Actually formulate_workflow_plan is pretty generic.
            # But the prompt says: "Erzeuge zwei harmlose abhängige Tasks." -> ChiefCommander should output steps.
        except Exception as e:
            print(f"Planner failed: {e}")
            return None

    plan = goal["workflow_plan"]
    idx = goal.get("current_step_index", 0)
    
    if idx < len(plan):
        next_task = plan[idx]
        goal["current_step_index"] = idx + 1
        return next_task
    else:
        goal["status"] = "DONE"
        return None

def dispatch_task(task):
    target = task["target_capability"]
    print(f"Dispatching {task['task_id']} to {target}")
    
    os.makedirs("tasks/dispatched", exist_ok=True)
    task_file = f"tasks/dispatched/{task['task_id']}.json"
    with open(task_file, 'w') as f:
        json.dump(task, f)
        
    task["status"] = "DISPATCHED"
    
    if target == "mac":
        subprocess.Popen(["python3", "scripts/mac_worker_adapter.py", task_file])
    elif target == "windows":
        subprocess.Popen(["python3", "scripts/windows_worker_adapter.py", task_file])
    else:
        task["status"] = "HUMAN_REQUIRED"
        
def process_results(state):
    os.makedirs("results/incoming", exist_ok=True)
    for res_file in glob.glob("results/incoming/*.json"):
        with open(res_file, 'r') as f:
            res = json.load(f)
        task_id = res["task_id"]
        if task_id in state["tasks"]:
            task = state["tasks"][task_id]
            task["status"] = "RESULT_RECEIVED"
            task["result"] = res
            
            if res.get("status") == "SUCCESS":
                task["status"] = "RECONCILED"
            else:
                task["status"] = "FAILED_TERMINAL"
                
            print(f"Task {task_id} reconciled to {task['status']}")
        os.remove(res_file)

def loop():
    state = load_state()
    ingest_goals(state)
    process_results(state)
    
    for goal_id, goal in state["goals"].items():
        if goal["status"] in ["NEW", "ACTIVE"]:
            goal["status"] = "ACTIVE"
            active_tasks = [t for t in state["tasks"].values() if t.get("goal_id") == goal_id and t["status"] not in ["RECONCILED", "FAILED_TERMINAL", "DONE"]]
            if not active_tasks:
                next_task = determine_next_task(goal_id, state)
                if next_task:
                    state["tasks"][next_task["task_id"]] = next_task
                    dispatch_task(next_task)
            
    save_state(state)

if __name__ == "__main__":
    loop()
