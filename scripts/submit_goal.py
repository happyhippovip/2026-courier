import argparse
import json
import uuid
import os
import datetime

def main():
    parser = argparse.ArgumentParser(description="Submit a new goal to the Courier Vollautomatik Control Plane")
    parser.add_argument("goal_text", type=str, help="The description of the goal to achieve")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pending_dir = os.path.join(project_root, "goals", "pending")
    os.makedirs(pending_dir, exist_ok=True)

    goal_id = f"goal_{uuid.uuid4().hex[:8]}"
    
    payload = {
        "goal_id": goal_id,
        "goal_text": args.goal_text,
        "status": "NEW",
        "created_at": datetime.datetime.now().isoformat()
    }

    filepath = os.path.join(pending_dir, f"{goal_id}.json")
    with open(filepath, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"Goal {goal_id} successfully submitted to {filepath}")

if __name__ == "__main__":
    main()
