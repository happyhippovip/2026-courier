import json, sys, os, time, shutil
from pathlib import Path

def dispatch(task_file):
    with open(task_file, 'r') as f:
        task = json.load(f)
    print(f"[Windows Transport] Routing task {task['task_id']} to Windows Worker DualTransport...")
    base_dir = Path("scripts/windows_worker")
    inbox = base_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    target_inbox_file = inbox / f"{task['task_id']}.json"
    shutil.copy(task_file, target_inbox_file)
    print(f"[Windows Transport] Task {task['task_id']} dropped in {target_inbox_file}.")

def ingest():
    base_dir = Path("scripts/windows_worker")
    outbox = base_dir / "outbox"
    if not outbox.exists(): return
    os.makedirs("results/incoming", exist_ok=True)
    for outbox_file in outbox.glob("*_result.json"):
        incoming = Path(f"results/incoming/{outbox_file.name}")
        incoming_tmp = incoming.with_suffix(".json.tmp")
        shutil.copy(outbox_file, incoming_tmp)
        os.replace(incoming_tmp, incoming)
        os.remove(outbox_file)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--ingest":
        ingest()
    elif len(sys.argv) > 1:
        dispatch(sys.argv[1])
