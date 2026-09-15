import json, sys, os, uuid
def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
    print(f"[Mac Worker] Loading canonical context and executing task {task['task_id']}")
    # Simulate agy headless execution for Canary
    res = {
        "goal_id": task.get("goal_id"),
        "task_id": task["task_id"],
        "worker_id": "MAC-01",
        "provider": "antigravity",
        "run_id": str(uuid.uuid4()),
        "status": "SUCCESS",
        "stdout_summary": f"Executed {task['description']} on Mac successfully"
    }
    os.makedirs("results/incoming", exist_ok=True)
    with open(f"results/incoming/{task['task_id']}_result.json", 'w') as f:
        json.dump(res, f)
if __name__ == "__main__":
    run(sys.argv[1])
