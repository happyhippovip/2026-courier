#!/usr/bin/env python3
"""CLI Entrypoint for the COURIER GENESIS ENGINE.

Usage:
    python scripts/courier_genesis_engine.py --mission GENESIS-001 --run
    python scripts/courier_genesis_engine.py --verify
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from courier_core.genesis_engine import CourierGenesisEngine, GenesisPolicy, TaskStatus


def run_genesis_demo(mission_id: str, state_dir: Path) -> dict:
    """Run an autonomous end-to-end demo of the Genesis Engine."""
    policy = GenesisPolicy(
        spend_limit_eur=0.0,
        single_writer=True,
        heavy_job_limit=1,
        allowed_origins=("https://example.org",),
    )
    engine = CourierGenesisEngine(mission_id=mission_id, policy=policy, state_dir=state_dir)

    # 1. Aufgaben erkennen: Decompose goal into tasks
    goal = {
        "type": "SEQUENTIAL_PIPELINE",
        "steps": [
            {
                "task_id": f"{mission_id}-task-a",
                "action_type": "EXECUTE_UNIT",
                "payload": {"expected_output": "UNIT_A_COMPLETED", "cost_eur": 0.0},
            },
            {
                "task_id": f"{mission_id}-task-b",
                "action_type": "SPIDER_CLAIM_VERIFY",
                "payload": {
                    "url": "https://example.org/quote",
                    "quote": "Courier Genesis Engine verified",
                    "approved_origin": "https://example.org",
                    "body": b"<html><body>Courier Genesis Engine verified evidence payload.</body></html>",
                    "cost_eur": 0.0,
                },
            },
            {
                "task_id": f"{mission_id}-task-c",
                "action_type": "EXECUTE_UNIT",
                "payload": {"expected_output": "UNIT_C_COMPLETED", "cost_eur": 0.0},
            },
        ],
    }
    engine.decompose_mission_goal(goal)

    # Mock executor simulating worker output
    def executor(task):
        if task.action_type == "EXECUTE_UNIT":
            expected = task.payload.get("expected_output", "OK")
            return {"exit_code": 0, "outputs": {"result": expected}}
        elif task.action_type == "SPIDER_CLAIM_VERIFY":
            return {"exit_code": 0}
        return {"exit_code": 0}

    # Run autonomous loop
    result = engine.run_autonomous_loop(executor=executor, worker_id="genesis-lead-worker")
    return result


def main():
    parser = argparse.ArgumentParser(description="Courier Genesis Engine CLI")
    parser.add_argument("--mission", default="GENESIS-ALPHA", help="Mission ID")
    parser.add_argument("--state-dir", default=".courier_genesis", help="State directory")
    parser.add_argument("--run", action="store_true", help="Run autonomous loop")
    parser.add_argument("--verify", action="store_true", help="Run self-verification test")
    args = parser.parse_args()

    state_path = Path(args.state_dir)
    res = run_genesis_demo(mission_id=args.mission, state_dir=state_path)
    print(json.dumps(res, indent=2))
    if not res.get("all_completed"):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
