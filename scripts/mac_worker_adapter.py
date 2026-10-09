import json, sys, os, time, shutil
from pathlib import Path

def _read_complete_json(path):
    """Return a JSON object only when the whole file is present.

    A writer that opens with mode 'w' creates an empty file before it dumps.
    Existence is not completion, and a second read can observe a later truncate.
    """
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        return None
    if not raw or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return value


def _publish_json(path, payload):
    """Publish one complete JSON object. Readers see the old file or the new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(json.dumps(payload).encode("utf-8"))
        handle.flush()
    os.replace(tmp, path)


def run(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
        
    print(f"[Mac Transport] Routing task {task['task_id']} to Mac Worker DualTransport...")
    
    base_dir = Path("scripts/mac_worker")
    inbox = base_dir / "inbox"
    outbox = base_dir / "outbox"
    
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    
    # Check if task explicitly needs native or AI
    # if not specified, default to ANTIGRAVITY for now, or detect based on some keyword.
    
    target_inbox_file = inbox / f"{task['task_id']}.json"
    shutil.copy(task_file, target_inbox_file)
    
    print(f"[Mac Transport] Task {task['task_id']} dropped in {target_inbox_file}. Waiting for result...")
    
    target_outbox_file = outbox / f"{task['task_id']}_result.json"
    incoming = Path("results/incoming") / f"{task['task_id']}_result.json"
    timeout = 300
    start = time.time()

    while True:
        payload = _read_complete_json(target_outbox_file)
        if payload is not None:
            break
        if time.time() - start > timeout:
            print(f"[Mac Transport] Timeout waiting for Mac worker to complete task {task['task_id']}.")
            _publish_json(incoming, {
                "status": "FAILED",
                "reason": "TIMEOUT",
                "goal_id": task.get("goal_id"),
                "task_id": task["task_id"]
            })
            return

        time.sleep(2)

    print(f"[Mac Transport] Received result for {task['task_id']} from Mac Worker!")
    # Publish the object already parsed. A later truncate of the outbox cannot empty it.
    _publish_json(incoming, payload)
    try:
        os.remove(target_outbox_file)
    except FileNotFoundError:
        pass

if __name__ == "__main__":
    run(sys.argv[1])
