import json
import os
import hashlib
import time
import subprocess
import sys
import fcntl

QUEUE_FILE = "muse_queue.json"
CHECKPOINT_FILE = "muse_checkpoint.json"
LOCK_FILE = "muse_runner.lock"

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def compute_fingerprint(task):
    content = f"{task['objective']}_{task['output_path']}_{task.get('input_refs', '')}"
    return hashlib.sha256(content.encode()).hexdigest()

def is_another_instance_running():
    lock_fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        return None

def main():
    lock_fd = is_another_instance_running()
    if not lock_fd:
        print("Another Muse runner is active. Exiting.")
        sys.exit(0)

    queue = load_json(QUEUE_FILE, [])
    checkpoint = load_json(CHECKPOINT_FILE, {"completed_fingerprints": []})

    has_work = True
    while has_work:
        queue = load_json(QUEUE_FILE, [])
        # Find next ready task
        task_idx = next((i for i, t in enumerate(queue) if t["status"] == "QUEUED"), None)
        if task_idx is None:
            print("Queue empty or no QUEUED tasks. IDLE/EXIT.")
            break

        task = queue[task_idx]
        fp = compute_fingerprint(task)
        task["fingerprint"] = fp

        if fp in checkpoint["completed_fingerprints"]:
            print(f"Task {task['task_id']} is duplicate. SKIPPING.")
            task["status"] = "SKIPPED_DUPLICATE"
            save_json(QUEUE_FILE, queue)
            continue

        print(f"Starting Task: {task['task_id']}")
        task["status"] = "RUNNING"
        save_json(QUEUE_FILE, queue)

        # Execute Muse
        prompt = (
            f"You are a READ-ONLY research agent. Objective: {task['objective']}. "
            f"Allowed scope: {task.get('allowed_scope', 'READ_ONLY')}. "
            f"Inputs: {task.get('input_refs', 'None')}. "
            f"Write your material findings to {task['output_path']}. "
            f"If there is no new information, write 'NO_DELTA'. "
            f"Return a JSON block anywhere in your output (or as your only output) with: "
            f'{{"sources": ["..."], "material_findings": "...", "recommended_action": "..."}}'
        )

        try:
            print(f"Executing agy for {task['task_id']}...")
            result = subprocess.run(
                ["agy", "--dangerously-skip-permissions", "-p", prompt],
                capture_output=True, text=True
            )
            # Find JSON block in output
            out = result.stdout + result.stderr
            # Fallback simple extraction
            import re
            json_match = re.search(r'\{.*"material_findings".*\}', out, re.DOTALL)
            parsed_res = {}
            if json_match:
                try:
                    parsed_res = json.loads(json_match.group(0))
                except Exception:
                    pass

            task["status"] = "COMPLETED"
            task["sources"] = parsed_res.get("sources", [])
            task["material_findings"] = parsed_res.get("material_findings", "See file")
            task["recommended_action"] = parsed_res.get("recommended_action", "None")
            task["completed_at"] = time.time()
            checkpoint["completed_fingerprints"].append(fp)
            
            # Ensure the output file exists even if the agent failed to create it
            if not os.path.exists(task['output_path']):
                with open(task['output_path'], 'w') as f:
                    f.write(out)

        except Exception as e:
            print(f"Task {task['task_id']} FAILED: {e}")
            task["status"] = "FAILED"
            task["error"] = str(e)

        save_json(QUEUE_FILE, queue)
        save_json(CHECKPOINT_FILE, checkpoint)

    os.close(lock_fd)

if __name__ == "__main__":
    main()
