from pathlib import Path
p = Path("server/app.py")
content = p.read_text()

# We need to replace the goal logic in approve_merge with the correct logic.
import re
target = """    goal = state["goals"].get(task.get("goal_id"))
    if goal:
        goal["current_step_index"] = goal.get("current_step_index", 0) + 1
        if goal["current_step_index"] >= len(goal.get("workflow_plan", [])):
            goal["status"] = "DONE"
        # Sync to workflow_plan
        for step in goal.get("workflow_plan", []):
            if step.get("task_id") == task_id:
                step["status"] = "RECONCILED"
                step["merge_approval"] = task["merge_approval"]

    save_state(state)"""

replacement = """    goal = state["goals"].get(task.get("goal_id"))
    if goal:
        # Sync to workflow_plan first
        for step in goal.get("workflow_plan", []):
            if step.get("task_id") == task_id:
                step["status"] = "RECONCILED"
                step["merge_approval"] = task["merge_approval"]

        all_done = True
        ready_work_exists = False
        completed_tasks = {
            step.get("task_id")
            for step in goal.get("workflow_plan", [])
            if step.get("status") == "RECONCILED"
        }
        for step in goal.get("workflow_plan", []):
            st = step.get("status")
            if st != "RECONCILED":
                all_done = False
            if st in ("QUEUED", "FAILED_TRANSIENT", "PROVIDER_WAIT"):
                deps = step.get("depends_on", [])
                if isinstance(deps, str): deps = [deps]
                if all(d in completed_tasks for d in deps):
                    ready_work_exists = True

        if all_done or (not ready_work_exists and goal.get("terminal") is False):
            if goal.get("terminal") is False:
                # Auto-Replenish!
                goal["replenish_count"] = goal.get("replenish_count", 0) + 1
                try:
                    from server.logic import ChiefCommander
                    _, planned_steps = ChiefCommander().formulate_workflow_plan(
                        goal["goal_text"], idea_type="GOAL"
                    )
                    if planned_steps:
                        for stp in planned_steps:
                            if "task_id" not in stp:
                                import uuid
                                stp["task_id"] = f"task-{uuid.uuid4().hex[:8]}"
                            stp["status"] = "QUEUED"
                            stp["attempts"] = 0
                            if "depends_on" not in stp:
                                stp["depends_on"] = list(completed_tasks)
                            state["tasks"][stp["task_id"]] = {
                                "goal_id": goal["goal_id"],
                                "task_id": stp["task_id"],
                                "status": "QUEUED",
                                "instruction": stp.get("instruction", ""),
                                "target_agent": stp.get("target_agent", "linux"),
                                "depends_on": stp.get("depends_on", []),
                                "attempts": 0,
                                "created_at": __import__('time').time()
                            }
                        goal["workflow_plan"].extend(planned_steps)
                        goal["status"] = "READY"
                    else:
                        goal["status"] = "DONE"
                except Exception as e:
                    print(f"Failed to auto-replenish in merge approval: {e}")
                    goal["status"] = "BLOCKED"
            else:
                goal["status"] = "DONE"

    save_state(state)"""

if target in content:
    content = content.replace(target, replacement)
    p.write_text(content)
    print("SUCCESS: Target found and replaced")
else:
    print("ERROR: Target not found")
