import re
from pathlib import Path

p = Path("scripts/agent_handoff_ledger.py")
content = p.read_text()

# We will add the tombstone parser
parser_target = """    cmd_update.add_argument("--lock-timeout", type=float, default=5.0)
    cmd_update.add_argument("--guard", type=Path, help="replacement acceptance guard JSON file")"""

parser_replacement = parser_target + """

    cmd_tombstone = subparsers.add_parser("tombstone", help="remove a blocked or hanging task from UNPROVEN_EDGES securely")
    cmd_tombstone.add_argument("ledger", type=Path)
    cmd_tombstone.add_argument("--edge", required=True, help="Edge to tombstone")
    cmd_tombstone.add_argument("--expected-revision", type=int, required=True)
    cmd_tombstone.add_argument("--updated-by", required=True)
    cmd_tombstone.add_argument("--lock-timeout", type=float, default=5.0)"""

if parser_target in content:
    content = content.replace(parser_target, parser_replacement)

# We will add the execution logic
main_target = """    elif args.command == "update":
        updates = {}
        for item in args.set:"""

main_replacement = """    elif args.command == "tombstone":
        def modify_tombstone(bundle: dict[str, Any]) -> None:
            if args.expected_revision != bundle["revision"]:
                raise RevisionConflictError(f"expected {args.expected_revision}, got {bundle['revision']}")
            record = bundle["record"]
            unproven = record.get("UNPROVEN_EDGES", [])
            if args.edge not in unproven:
                print(f"Edge {args.edge} not found in UNPROVEN_EDGES.")
                return
            unproven.remove(args.edge)
            record["UNPROVEN_EDGES"] = unproven
            
        update_ledger(args.ledger, modify_tombstone, args.updated_by, args.lock_timeout)
        print("Tombstoned securely.")

    elif args.command == "update":
        updates = {}
        for item in args.set:"""

if main_target in content:
    content = content.replace(main_target, main_replacement)

p.write_text(content)
print("SUCCESS")
