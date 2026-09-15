import json
import os
import sys

sys.path.insert(0, r"C:\Users\lol\2026-workspace\courier")

from chief.goal_reconciler import GoalReconciler
from chief.control_plane import ControlPlane

BACKLOG_PATH = r"C:\Users\lol\2026-workspace\project-memory\data\safe_backlog.json"

db_path = r"C:\Users\lol\2026-workspace\project-memory\data\courier_control_plane.sqlite"
if os.path.exists(db_path):
    os.remove(db_path)

initial_state = {
    "version": "1.0.0",
    "last_updated": "2026-09-15T00:00:00Z",
    "machine_role": "WINDOWS_PARALLEL_COMMERCIAL",
    "spend_limit_eur": 0.0,
    "verified_real_revenue_eur": 0.0,
    "tasks": [
        {
            "task_id": "TASK-FINAL-A",
            "title": "Create a python script C:\\Users\\lol\\2026-workspace\\project-memory\\data\\spawn_b.py containing code to load C:\\Users\\lol\\2026-workspace\\project-memory\\data\\safe_backlog.json, append a dict {'task_id': 'TASK-FINAL-B', 'title': 'Print Task B success and exit', 'status': 'PENDING'} to tasks array, and save it. Run spawn_b.py. Output EXACTLY: LOCAL_STEP_ERLEDIGT: JA and GESAMTAUFGABE_ERLEDIGT: JA",
            "category": "AUTONOMY_GAP_CLOSURE",
            "goal_impact": 10.0,
            "information_gain": 10.0,
            "revenue_impact": 10.0,
            "time_to_result_min": 1,
            "dependencies": [],
            "collision_risk": 0.0,
            "reversibility": 1.0,
            "external_action_risk": 0.0,
            "human_requirement": "NONE",
            "status": "PENDING"
        }
    ]
}

with open(BACKLOG_PATH, 'w', encoding='utf-8') as f:
    json.dump(initial_state, f, indent=2)

print("[-] Task A initialized in safe_backlog.json")

cp = ControlPlane()
reconciler = GoalReconciler(cp=cp)

for i in range(3):
    print(f"\n[-] Cycle {i+1} START")
    try:
        res = reconciler.reconcile_and_execute(max_tasks_per_cycle=1)
        print(f"[-] Cycle {i+1} handled: {res}")
    except Exception as e:
        print(f"[-] Cycle {i+1} ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    with open(BACKLOG_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        tasks = [(t['task_id'], t.get('status')) for t in data.get('tasks', [])]
        print(f"[-] Current backlog tasks: {tasks}")
    
    pending = [t for t, s in tasks if s == 'PENDING']
    if not pending:
        print("[-] Backlog empty of pending tasks, safe quiescence achieved.")
        break
