import os, json, glob, time, uuid, subprocess, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_chief_commander import ChiefCommander
from integration_contract import ContractError, prepare_task, verify_result

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
    temp_path = f"{STATE_FILE}.tmp"
    with open(temp_path, 'w') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, STATE_FILE)

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
                
                # GitHub-hosted ephemeral für Repo-Arbeit by default
                target_cap = "github"
                
                # Self-hosted Runner nur bei echter lokaler Capability
                if "mac" in target_agent:
                    target_cap = "mac"
                elif "desktop" in target_agent or "local" in target_agent or "windows" in target_agent:
                    target_cap = "windows_desktop"
                
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

def dispatch_task(task, state=None):
    task.update(prepare_task(task))
    target = task["target_capability"]
    print(f"Dispatching {task['task_id']} to {target}")
    task["status"] = "DISPATCHED"
    
    os.makedirs("tasks/dispatched", exist_ok=True)
    task_file = f"tasks/dispatched/{task['task_id']}.json"
    with open(task_file, 'w') as f:
        json.dump(task, f)
        f.flush()
        os.fsync(f.fileno())

    # Persist DISPATCHED before an external worker can observe the packet.
    if state is not None:
        save_state(state)
    
    if target in ["mac", "windows", "github"]:
        subprocess.Popen([sys.executable, "scripts/github_worker_adapter.py", task_file])
    else:
        task["status"] = "HUMAN_REQUIRED"
        
def process_results(state):
    os.makedirs("results/incoming", exist_ok=True)
    os.makedirs("results/processed", exist_ok=True)
    os.makedirs("results/rejected", exist_ok=True)
    workspace = Path.cwd()
    for res_file in glob.glob("results/incoming/*.json"):
        source_path = Path(res_file)
        accepted = False
        try:
            res = json.loads(source_path.read_text(encoding="utf-8"))
            task_id = res.get("task_id")
            if task_id not in state["tasks"]:
                raise ContractError("result references unknown task")
            task = state["tasks"][task_id]
            if task.get("status") in {"RECONCILED", "FAILED_TERMINAL", "FAILED_VERIFICATION"}:
                raise ContractError("duplicate terminal result")
            task["status"] = "RESULT_RECEIVED"
            durable_result = verify_result(task, res, workspace)
            task["result"] = durable_result
            task["run_id"] = durable_result["run_id"]
            task["result_id"] = durable_result["result_id"]
            if durable_result["status"] == "SUCCESS":
                task["status"] = "RECONCILED"
                print(f"Verification PASS: {durable_result['result_id']}")
            elif durable_result["status"] == "AUTH_REQUIRED":
                task["status"] = "WAITING_FOR_PROVIDER"
                print(f"Task {task['task_id']} WAITING_FOR_PROVIDER (Auth required)")
            elif durable_result["status"] == "WAITING_FOR_WORKER":
                task["status"] = "WAITING_FOR_WORKER"
                print(f"Task {task['task_id']} WAITING_FOR_WORKER (Worker offline or timeout)")
            elif durable_result.get("reason") == "LEASE_EXPIRED":
                task["status"] = "LEASE_EXPIRED"
                print(f"Task {task['task_id']} LEASE_EXPIRED (Process/OS restart or crash)")
            else:
                task["status"] = "FAILED_TERMINAL"
                state["goals"][task["goal_id"]]["status"] = "BLOCKED"
            target = Path("results/processed") / f"{durable_result['result_id']}.json"
            temp_target = target.with_suffix(".json.tmp")
            temp_target.write_text(json.dumps(durable_result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            os.replace(temp_target, target)
            # Persist reconciliation before acknowledging/removing the inbox item.
            save_state(state)
            accepted = True
        except (OSError, json.JSONDecodeError, ContractError) as exc:
            task_id = None
            try:
                task_id = json.loads(source_path.read_text(encoding="utf-8")).get("task_id")
            except (OSError, json.JSONDecodeError):
                pass
            if task_id in state["tasks"] and state["tasks"][task_id].get("status") not in {
                "RECONCILED", "FAILED_TERMINAL", "FAILED_VERIFICATION"
            }:
                task = state["tasks"][task_id]
                task["status"] = "FAILED_VERIFICATION"
                state["goals"][task["goal_id"]]["status"] = "BLOCKED"
                save_state(state)
            print(f"Verification FAIL: {exc}")
        finally:
            if accepted:
                source_path.unlink(missing_ok=True)
            elif source_path.exists():
                rejected = Path("results/rejected") / source_path.name
                if rejected.exists():
                    rejected = rejected.with_name(f"{rejected.stem}-{uuid.uuid4().hex}{rejected.suffix}")
                os.replace(source_path, rejected)

def ingest_adapters():
    # Legacy manual ingestion (e.g. windows_worker_adapter.py --ingest) is removed.
    # The github_worker_adapter pulls artifacts and places them directly into results/incoming/
    pass

def loop():
    state = load_state()
    ingest_goals(state)
    ingest_adapters()
    process_results(state)
    
    for task_id, task in state["tasks"].items():
        if task.get("status") in ["WAITING_FOR_PROVIDER", "LEASE_EXPIRED", "QUEUED", "WAITING_FOR_WORKER"]:
            print(f"Dispatching task {task_id} from state {task.get('status')}...")
            task["status"] = "QUEUED"
            dispatch_task(task, state)
            
    for goal_id, goal in state["goals"].items():
        if goal["status"] in ["NEW", "ACTIVE"]:
            goal["status"] = "ACTIVE"
            active_tasks = [t for t in state["tasks"].values() if t.get("goal_id") == goal_id and t["status"] not in ["RECONCILED", "FAILED_TERMINAL", "DONE"]]
            if not active_tasks:
                next_task = determine_next_task(goal_id, state)
                if next_task:
                    next_task = prepare_task(next_task)
                    state["tasks"][next_task["task_id"]] = next_task
                    dispatch_task(next_task, state)
            
    save_state(state)

if __name__ == "__main__":
    if "--daemon" in sys.argv:
        print("Starting Courier Control Plane Daemon...")
        # Recover dispatched tasks on daemon startup
        state = load_state()
        recovered = False
        for task in state["tasks"].values():
            if task.get("status") == "DISPATCHED":
                task["status"] = "QUEUED"
                recovered = True
        if recovered:
            save_state(state)
            
        while True:
            loop()
            time.sleep(5)
    else:
        loop()
