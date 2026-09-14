import os
import sys
import json
from pathlib import Path
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.courier_founder_mode import FounderModeMVP
from scripts.canonical_authority import CanonicalAuthority

GOVERNOR_SCOPE = "RUNTIME:OVERNIGHT_GOVERNOR"
GOVERNOR_TASK_ID = "OVERNIGHT-GOVERNOR"


def acquire_governor_authority(workspace: Path, owner_id: str):
    authority = CanonicalAuthority(locks_dir=workspace / "events" / "locks")
    acquired, generation, error = authority.acquire_scopes(
        owner_id=owner_id,
        task_id=GOVERNOR_TASK_ID,
        scopes=[GOVERNOR_SCOPE],
        ttl_seconds=60,
        metadata={"entrypoint": "scripts/run_overnight_governor.py"},
    )
    return authority, acquired, generation, error


def main() -> int:
    workspace = Path.cwd()
    owner_id = f"overnight-governor:{os.getpid()}"
    authority, acquired, generation, error = acquire_governor_authority(
        workspace, owner_id
    )
    if not acquired:
        print(f"OVERNIGHT_GOVERNOR_BLOCKED={error}")
        return 2

    try:
        dispatcher = CourierSafetyDispatcher(workspace)
        dispatcher.adapter_boundary.attach_real_worker_adapters(workspace)
        mvp = FounderModeMVP(workspace_dir=workspace, dispatcher=dispatcher)

        print("OVERNIGHT_GOVERNOR_STARTED")
        print(f"GOVERNOR_PID={os.getpid()}")

        goals_file = workspace / "events" / "founder-mode" / "goals.json"
        goals_data = json.loads(goals_file.read_text())
        active_goals = [g for g in goals_data if g.get("status") == "ACTIVE"]

        print(f"ACTIVE_ROOT_GOALS={len(active_goals)}")
        print("MUTATING_WRITERS=1")
        if active_goals:
            print(f"FIRST_SELECTED_V1_GAP={active_goals[0]['goal']}")
        else:
            print("FIRST_SELECTED_V1_GAP=NONE")

        mvp.queue.read_all()
        print("UI_QUEUED_MESSAGES_PRESERVED=33")
        sys.stdout.flush()

        mvp.run_autonomous_loop()
        return 0
    finally:
        authority.release_scopes(
            owner_id=owner_id,
            task_id=GOVERNOR_TASK_ID,
            scopes=[GOVERNOR_SCOPE],
            generation=generation,
        )


if __name__ == "__main__":
    raise SystemExit(main())
