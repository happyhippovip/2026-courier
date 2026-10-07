import argparse
from scripts.github_coordination import GitHubCoordinationAdapter
from scripts.coordination_ledger import CoordinationReducer

def main():
    parser = argparse.ArgumentParser(description="Courier Coordination Status CLI")
    parser.add_argument("--repo", required=True, help="GitHub repository (e.g. happyhippovip/2026-courier)")
    parser.add_argument("--issue", type=int, required=True, help="GitHub issue number acting as the ledger")
    parser.add_argument("--mission", help="Optional mission ID to inspect")
    args = parser.parse_args()

    adapter = GitHubCoordinationAdapter(args.repo, args.issue)
    events = adapter.read_events()
    
    reducer = CoordinationReducer()
    for event in events:
        reducer.apply(event)
        
    if args.mission:
        mission = reducer.get_mission(args.mission)
        if not mission:
            print(f"Mission '{args.mission}' not found.")
            return
        print(f"Mission: {mission['mission_id']}")
        print(f"Agent: {mission['agent_id']}")
        print(f"Host: {mission['host_id']}")
        print(f"Status: {mission['status']}")
        print(f"Evidence: {mission['evidence_ref']}")
    else:
        missions = reducer.get_all_missions()
        if not missions:
            print("No missions found in the ledger.")
            return
        
        print(f"{'MISSION':<20} | {'AGENT':<20} | {'STATUS':<15} | {'EVIDENCE'}")
        print("-" * 80)
        for mid, m in missions.items():
            print(f"{mid:<20} | {m['agent_id']:<20} | {m['status'].value:<15} | {m['evidence_ref']}")

if __name__ == "__main__":
    main()
