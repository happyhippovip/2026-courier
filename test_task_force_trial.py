import os
import json
import uuid
import time
from chief.control_plane import ControlPlane
from chief.scheduled_cycle import execute_windows_validation_cycle

def main():
    trial_id = uuid.uuid4().hex
    db_path = f"test_trial_{trial_id}.sqlite"
    handoffs_dir = f"C:\\Users\\lol\\2026-workspace\\courier\\test_handoffs_{trial_id}"
    os.makedirs(handoffs_dir, exist_ok=True)
    
    cp = ControlPlane(db_path=db_path)
    
    # TASK 1
    t1 = {
        "mission_id": "MISSION-AUTONOMY",
        "windows_validation_request_id": "TASK-1",
        "artifact_reference": "git",
        "exact_question": f"Run a command to get the current git branch name and HEAD commit in C:\\Users\\lol\\2026-workspace\\courier. Then, write a valid JSON file to {handoffs_dir}\\REQUEST_TASK-3.json that contains exactly this JSON: {{\"mission_id\": \"MISSION-AUTONOMY\", \"windows_validation_request_id\": \"TASK-3\", \"artifact_reference\": \"none\", \"exact_question\": \"Output LOCAL_STEP_ERLEDIGT: TRUE\", \"expected_evidence\": \"branch and commit\", \"allowed_scope\": \"C:\\\\Users\\\\lol\\\\2026-workspace\"}}. Then output LOCAL_STEP_ERLEDIGT: TRUE",
        "expected_evidence": "Branch and HEAD",
        "allowed_scope": "C:\\Users\\lol\\2026-workspace"
    }
    
    # TASK 2
    t2 = {
        "mission_id": "MISSION-AUTONOMY",
        "windows_validation_request_id": "TASK-2",
        "artifact_reference": "README.md",
        "exact_question": "Read C:\\Users\\lol\\2026-workspace\\courier\\START-HERE.md. Output its first word. Then output LOCAL_STEP_ERLEDIGT: TRUE",
        "expected_evidence": "First word",
        "allowed_scope": "C:\\Users\\lol\\2026-workspace"
    }
    
    # TASK 4
    t4 = {
        "mission_id": "MISSION-AUTONOMY",
        "windows_validation_request_id": "TASK-4",
        "validation_type": "DARWIN_TEST",
        "artifact_reference": "none",
        "exact_question": "Do something on Mac",
        "expected_evidence": "None",
        "allowed_scope": "C:\\Users\\lol\\2026-workspace"
    }
    
    # TASK 5A
    t5a = {
        "mission_id": "MISSION-AUTONOMY",
        "windows_validation_request_id": "TASK-5",
        "assignment_id": "ASSIGN-5",
        "artifact_reference": "none",
        "exact_question": "Output LOCAL_STEP_ERLEDIGT: TRUE",
        "expected_evidence": "success",
        "allowed_scope": "C:\\Users\\lol\\2026-workspace"
    }
    
    # TASK 5B
    t5b = {
        "mission_id": "MISSION-AUTONOMY",
        "windows_validation_request_id": "TASK-5-FAKE",
        "assignment_id": "ASSIGN-5",
        "artifact_reference": "none",
        "exact_question": "Output LOCAL_STEP_ERLEDIGT: TRUE",
        "expected_evidence": "success",
        "allowed_scope": "C:\\Users\\lol\\2026-workspace"
    }
    
    with open(os.path.join(handoffs_dir, "REQUEST_TASK-1.json"), "w") as f:
        json.dump(t1, f)
    with open(os.path.join(handoffs_dir, "REQUEST_TASK-2.json"), "w") as f:
        json.dump(t2, f)
    with open(os.path.join(handoffs_dir, "REQUEST_TASK-4.json"), "w") as f:
        json.dump(t4, f)
    with open(os.path.join(handoffs_dir, "REQUEST_TASK-5A.json"), "w") as f:
        json.dump(t5a, f)
    with open(os.path.join(handoffs_dir, "REQUEST_TASK-5B.json"), "w") as f:
        json.dump(t5b, f)
        
    print("Starting cycles...")
    for i in range(10):
        print(f"Cycle {i+1}")
        try:
            res = execute_windows_validation_cycle(handoffs_dir=handoffs_dir, cp=cp)
            print(res)
            if res.get("quiescent"):
                print("Queue is empty, quiescent.")
                break
        except Exception as e:
            print(f"Cycle Exception: {e}")
            
    # Print summary
    tasks = cp.get_all_tasks()
    for t in tasks:
        print(f"Task {t['task_id']}: {t['status']} (Assignment: {t.get('assignment_id')})")

if __name__ == "__main__":
    main()
