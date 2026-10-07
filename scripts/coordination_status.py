import argparse
import json
import sys

from scripts.github_coordination import GitHubCoordinationAdapter, FileCoordinationStore
from scripts.coordination_ledger import AgentID, CoordinationReducer, HostID
from scripts.coordination_resume import (
    CLAIMED,
    claim_mission,
    discover_resumable,
)


def _parse_enum(enum_cls, value):
    try:
        return enum_cls(value)
    except ValueError:
        return enum_cls.UNKNOWN


def main(argv=None):
    parser = argparse.ArgumentParser(description="Courier Coordination Status CLI")
    parser.add_argument("--repo", help="GitHub repository (e.g. happyhippovip/2026-courier)")
    parser.add_argument("--issue", type=int, help="GitHub issue number acting as the ledger")
    parser.add_argument("--events-file", help="JSONL coordination ledger mirror (offline shared truth)")
    parser.add_argument("--mission", help="Optional mission ID to inspect")
    parser.add_argument("--agent", help="Worker identity for --discover/--claim")
    parser.add_argument("--host", help="Host identity for --claim")
    parser.add_argument("--discover", action="store_true", help="Print resumable checkpoints for --agent as JSON")
    parser.add_argument("--claim", metavar="MISSION", help="Claim/resume MISSION for --agent/--host; prints JSON")
    args = parser.parse_args(argv)

    if args.events_file:
        store = FileCoordinationStore(args.events_file)
    elif args.repo and args.issue:
        store = GitHubCoordinationAdapter(args.repo, args.issue)
    else:
        parser.error("either --events-file or --repo/--issue is required")

    if args.discover or args.claim:
        agent = _parse_enum(AgentID, args.agent)
        if args.claim:
            result = claim_mission(store, agent, _parse_enum(HostID, args.host), args.claim)
            print(json.dumps(result.to_dict(), sort_keys=True))
            return 0 if result.outcome == CLAIMED else 2
        reducer = CoordinationReducer()
        for event in store.read_events():
            reducer.apply(event)
        print(json.dumps([c.to_dict() for c in discover_resumable(reducer, agent)], sort_keys=True))
        return 0

    events = store.read_events()

    reducer = CoordinationReducer()
    for event in events:
        reducer.apply(event)

    if args.mission:
        mission = reducer.get_mission(args.mission)
        if not mission:
            print(f"Mission '{args.mission}' not found.")
            return 1
        print(f"Mission: {mission['mission_id']}")
        print(f"Agent: {mission['agent_id']}")
        print(f"Host: {mission['host_id']}")
        print(f"Status: {mission['status']}")
        print(f"Evidence: {mission['evidence_ref']}")
    else:
        missions = reducer.get_all_missions()
        if not missions:
            print("No missions found in the ledger.")
            return 0

        print(f"{'MISSION':<20} | {'AGENT':<20} | {'STATUS':<15} | {'EVIDENCE'}")
        print("-" * 80)
        for mid, m in missions.items():
            print(f"{mid:<20} | {m['agent_id'].value:<20} | {m['status'].value:<15} | {m['evidence_ref']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
