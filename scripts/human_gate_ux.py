#!/usr/bin/env python3
"""Interactive & Programmatic Human Gate Approval UX.

Prompts operators to review and authorize protected actions (external effects,
deployments, irreversible ledger transactions).
"""

import argparse
import datetime
import getpass
import json
import os
import sys
import tempfile
from pathlib import Path


def run_human_gate(
    payload_file: str,
    decision: str | None = None,
    auto_reject_non_interactive: bool = True,
    quiet: bool = False,
) -> dict | None:
    """Evaluates a human gate request with atomic receipt generation."""
    path = Path(payload_file).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Human gate payload file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not quiet:
        print("\n" + "=" * 50)
        print("🚨 HUMAN GATE APPROVAL REQUIRED 🚨")
        print("=" * 50)
        print(f"ACTION PROPOSED:  {data.get('action')}")
        print(f"ARTIFACTS/CODE:   {', '.join(data.get('artifacts', []))}")
        print(f"WHY REQUIRED:     {data.get('reason')}")
        print("=" * 50)

    while True:
        if decision:
            resp = decision.strip().upper()
        else:
            try:
                resp = input("Do you approve this action? (APPROVE/REJECT): ").strip().upper()
            except EOFError:
                if auto_reject_non_interactive:
                    if not quiet:
                        print("Non-interactive environment detected. Auto-rejecting protected action.")
                    return None
                resp = "REJECT"

        if resp == "APPROVE":
            try:
                identity = getpass.getuser()
            except Exception:
                identity = os.environ.get("USERNAME", os.environ.get("USER", "courier-operator"))
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if not quiet:
                print(f"\n[+] Action APPROVED by {identity} at {timestamp}")

            # Record approval atomically
            approval_record = {
                "status": "APPROVED",
                "identity": identity,
                "timestamp": timestamp,
                "action": data.get("action"),
            }
            approval_file = path.with_suffix(path.suffix + ".approval")
            fd, tmp_file = tempfile.mkstemp(dir=approval_file.parent, prefix="gate_", suffix=".tmp")
            with open(fd, "w", encoding="utf-8") as out:
                json.dump(approval_record, out, indent=2)
            os.replace(tmp_file, approval_file)

            return approval_record
        elif resp == "REJECT":
            if not quiet:
                print("\n[-] Action REJECTED.")
            return None
        else:
            if not quiet:
                print("Please type 'APPROVE' or 'REJECT'.")
            if decision:
                return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Human Gate Approval UX")
    parser.add_argument("payload_file", help="Path to gate_payload.json")
    parser.add_argument("--decision", choices=["APPROVE", "REJECT"], help="Programmatic decision")
    parser.add_argument("--json", action="store_true", help="Print approval JSON on success")
    args = parser.parse_args(argv)

    record = run_human_gate(args.payload_file, decision=args.decision, quiet=args.json)
    if record:
        if args.json:
            print(json.dumps(record, indent=2))
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
