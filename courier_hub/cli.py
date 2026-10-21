"""Hub command line.

``courier-hub`` with no subcommand starts the desktop hub server.
``courier-hub install-status`` prints one host's installation card as JSON.
That card is derived by courier_hub.model from the install-state contract.
It does not read a success message from an installer script.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from courier_core.install_state import Evidence, JournalUnreadable, scrub_secrets
from courier_hub import model

from .server import main as _main


def evidence_from_mapping(raw: dict) -> Evidence:
    """Keep only evidence fields. Extra keys, including secrets, are dropped."""
    if not isinstance(raw, dict):
        raise JournalUnreadable("evidence is not an object")
    cleaned = scrub_secrets(raw)
    confirmed = cleaned.get("controller_confirmed_at")
    if isinstance(confirmed, str) and confirmed:
        confirmed = datetime.fromisoformat(confirmed)
    elif confirmed is not None and not isinstance(confirmed, datetime):
        confirmed = None
    identity = cleaned.get("process_identity")
    if not isinstance(identity, dict):
        identity = None
    worker = cleaned.get("controller_worker_id")
    if not isinstance(worker, str) or worker == "[redacted]":
        worker = None
    return Evidence(
        config_present=bool(cleaned.get("config_present")),
        runtime_present=bool(cleaned.get("runtime_present")),
        scheduler_registered=bool(cleaned.get("scheduler_registered")),
        scheduler_principal=_text(cleaned.get("scheduler_principal")),
        current_user=_text(cleaned.get("current_user")),
        process_alive=bool(cleaned.get("process_alive")),
        process_identity=identity,
        controller_worker_id=worker,
        controller_confirmed_at=confirmed,
    )


def load_evidence(path) -> Evidence:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return evidence_from_mapping(document)


def install_status_text(state_dir, evidence, now, *, host_id: str = "this-computer") -> str:
    card = model.host_installation(state_dir, evidence, now, host_id=host_id)
    return json.dumps(card, sort_keys=True)


def install_status_cli(argv) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="courier-hub install-status")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--host", default="this-computer")
    args = parser.parse_args(argv)
    try:
        evidence = load_evidence(args.evidence)
        now = datetime.fromisoformat(args.now)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, JournalUnreadable):
        card = model.host_installation(args.state_dir, Evidence(), datetime.now().astimezone(), host_id=args.host)
        # A bad evidence file is not a readable status input.
        card = {
            "host_id": card["host_id"],
            "bucket": "unknown",
            "tone": "needs_human",
            "label": "Unknown — needs a person",
            "reason_code": "STATUS_UNREADABLE",
            "contract_state": None,
            "version": None,
        }
        sys.stdout.write(json.dumps(card, sort_keys=True) + "\n")
        return 0
    sys.stdout.write(install_status_text(args.state_dir, evidence, now, host_id=args.host) + "\n")
    return 0


def _text(value):
    if not isinstance(value, str) or value == "[redacted]":
        return None
    return value


def main(argv=None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) > 1 and args[1] == "install-status":
        return install_status_cli(args[2:])
    return _main(args)


if __name__ == "__main__":
    sys.exit(main())
