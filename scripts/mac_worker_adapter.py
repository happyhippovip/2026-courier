import json, sys, os, re, time, shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent / "mac_worker"

_SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)

    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not _SAFE_TASK_ID.match(task_id):
        print(f"[Mac Transport] Refusing task with unsafe task_id: {task_id!r}.")
        return 2

    print(f"[Mac Transport] Routing task {task_id} to Mac Worker DualTransport...")

    inbox = BASE_DIR / "inbox"
    outbox = BASE_DIR / "outbox"
    results_dir = Path("results/incoming")

    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    # Check if task explicitly needs native or AI
    # if not specified, default to ANTIGRAVITY for now, or detect based on some keyword.

    target_inbox_file = inbox / f"{task_id}.json"
    shutil.copy(task_file, target_inbox_file)

    print(f"[Mac Transport] Task {task_id} dropped in {target_inbox_file}. Waiting for result...")

    target_outbox_file = outbox / f"{task_id}_result.json"
    # A leftover result from an earlier attempt must never bind to this run.
    if target_outbox_file.exists():
        print(f"[Mac Transport] Removing stale outbox result for {task_id}.")
        target_outbox_file.unlink()
    timeout = 300
    start = time.time()

    while True:
        if target_outbox_file.exists():
            break
        if time.time() - start > timeout:
            print(f"[Mac Transport] Timeout waiting for Mac worker to complete task {task_id}.")
            res = {
                "status": "FAILED",
                "reason": "TIMEOUT",
                "goal_id": task.get("goal_id"),
                "task_id": task_id
            }
            incoming = results_dir / f"{task_id}_result.json"
            incoming_tmp = incoming.with_suffix(".json.tmp")
            with open(incoming_tmp, 'w') as f:
                json.dump(res, f)
            os.replace(incoming_tmp, incoming)
            return 1

        time.sleep(2)

    print(f"[Mac Transport] Received result for {task_id} from Mac Worker!")
    incoming = results_dir / f"{task_id}_result.json"
    incoming_tmp = incoming.with_suffix(".json.tmp")
    shutil.copy(target_outbox_file, incoming_tmp)
    os.replace(incoming_tmp, incoming)
    os.remove(target_outbox_file)
    return 0

if __name__ == "__main__":
    sys.exit(run(sys.argv[1]))
