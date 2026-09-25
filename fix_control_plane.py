import json, os, uuid, sys

def patch_control_plane():
    with open("scripts/courier_control_plane.py", "r") as f:
        content = f.read()

    new_determine_next_task = """
def determine_next_task(goal_id, state):
    goal = state["goals"][goal_id]
    goal_text = goal["goal_text"]
    
    # Check if we already formulated a workflow plan for this goal
    if "workflow_plan" not in goal:
        # Use existing ChiefCommander to formulate plan (REUSING EXISTING PLANNER)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            from run_chief_commander import ChiefCommander
            chief = ChiefCommander()
            print(f"Formulating plan for goal {goal_id} using ChiefCommander...")
            wf_id, plan = chief.formulate_workflow_plan(goal_text, idea_type="GOAL")
            
            # Map the plan to Courier tasks
            mapped_plan = []
            for i, step in enumerate(plan):
                mapped_plan.append({
                    "task_id": step["task_id"],
                    "goal_id": goal_id,
                    "description": step["instruction"],
                    "target_capability": "mac", # Default to mac for canary to ensure real execution
                    "status": "QUEUED"
                })
            goal["workflow_plan"] = mapped_plan
            goal["current_step_index"] = 0
            
        except Exception as e:
            print(f"Failed to formulate plan: {e}")
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
"""

    import re
    # Replace the existing determine_next_task function
    pattern = re.compile(r"def determine_next_task\(goal_id, state\):.*?return None", re.DOTALL)
    
    # Fallback if pattern matching is tricky: Just reconstruct the file
    pass

if __name__ == "__main__":
    patch_control_plane()
