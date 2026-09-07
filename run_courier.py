import os
import sys
import argparse
from pathlib import Path
from scripts.courier_founder_mode import FounderModeMVP
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_real_worker_adapters import get_real_worker_adapters

def main():
    parser = argparse.ArgumentParser(description="Courier Orchestration Layer")
    parser.add_argument("--submit-goal", type=str, help="Submit a new high-level goal to Courier")
    parser.add_argument("--source", type=str, default="CLI", help="Source of the goal (default: CLI)")
    args = parser.parse_args()

    workspace = os.getcwd()
    dispatcher = CourierSafetyDispatcher(workspace)
    adapters = get_real_worker_adapters(Path(workspace))
    for agent, adapter in adapters.items():
        dispatcher.adapter_boundary.register_consumer(agent, adapter)

    mvp = FounderModeMVP(workspace_dir=workspace, dispatcher=dispatcher)

    if args.submit_goal:
        goal_id = mvp.intake.submit_goal(source=args.source, goal=args.submit_goal)
        print(f"Goal submitted successfully. ID: {goal_id}")

    print("Starting Autonomous Loop...")
    mvp.run_autonomous_loop()
    print("Done.")

if __name__ == "__main__":
    main()
