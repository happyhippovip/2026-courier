import json
import os
import hashlib
import time
import subprocess
import sys
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_QUEUE_FILE = BASE_DIR / "muse_queue.json"
DEFAULT_CHECKPOINT_FILE = BASE_DIR / "muse_checkpoint.json"
DEFAULT_LOCK_FILE = BASE_DIR / "muse_runner.lock"
DEFAULT_TIMEOUT = int(os.environ.get("MUSE_RUNNER_TIMEOUT", "180"))


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Quarantine corrupt file to preserve forensics
        try:
            corrupt_path = p.with_name(f"{p.name}.corrupt.{int(time.time())}")
            p.replace(corrupt_path)
        except OSError:
            pass
        return default


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp_path = p.with_name(f".{p.name}.tmp.{os.getpid()}.{int(time.time() * 1000)}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(p)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def compute_fingerprint(task):
    content = f"{task['objective']}_{task['output_path']}_{task.get('input_refs', '')}"
    return hashlib.sha256(content.encode()).hexdigest()


def acquire_lock(lock_path):
    lock_p = Path(lock_path)
    lock_p.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        try:
            import msvcrt
            fd = os.open(str(lock_p), os.O_RDWR | os.O_CREAT)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return fd
        except (ImportError, OSError, IOError):
            return None
    else:
        try:
            import fcntl
            fd = os.open(str(lock_p), os.O_RDWR | os.O_CREAT)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except (ImportError, OSError, BlockingIOError):
            return None


def release_lock(fd):
    if fd is not None:
        try:
            if sys.platform == "win32":
                try:
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except (ImportError, OSError, IOError):
                    pass
            else:
                try:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except (ImportError, OSError):
                    pass
            os.close(fd)
        except OSError:
            pass


def is_another_instance_running(lock_path=None):
    lp = lock_path or os.environ.get("MUSE_LOCK_FILE", str(DEFAULT_LOCK_FILE))
    return acquire_lock(lp)


def resolve_output_path(base_dir, out_path_str):
    target = (Path(base_dir) / out_path_str).resolve()
    base_resolved = Path(base_dir).resolve()
    if not (target == base_resolved or base_resolved in target.parents):
        raise ValueError(f"Scope escape detected in output_path: {out_path_str}")
    return target


def run_muse_cycle(queue_path=None, checkpoint_path=None, timeout=DEFAULT_TIMEOUT,
                   runner_cmd=None, base_dir=None):
    bdir = Path(base_dir) if base_dir else BASE_DIR
    q_path = Path(queue_path) if queue_path else Path(os.environ.get("MUSE_QUEUE_FILE", DEFAULT_QUEUE_FILE))
    cp_path = Path(checkpoint_path) if checkpoint_path else Path(os.environ.get("MUSE_CHECKPOINT_FILE", DEFAULT_CHECKPOINT_FILE))

    queue = load_json(q_path, [])
    checkpoint = load_json(cp_path, {"completed_fingerprints": []})

    processed_count = 0
    while True:
        queue = load_json(q_path, [])
        task_idx = next((i for i, t in enumerate(queue) if t.get("status") == "QUEUED"), None)
        if task_idx is None:
            break

        task = queue[task_idx]
        fp = compute_fingerprint(task)
        task["fingerprint"] = fp

        if fp in checkpoint.get("completed_fingerprints", []):
            task["status"] = "SKIPPED_DUPLICATE"
            save_json(q_path, queue)
            processed_count += 1
            continue

        task["status"] = "RUNNING"
        save_json(q_path, queue)

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
            out_file = resolve_output_path(bdir, task["output_path"])
            out_file.parent.mkdir(parents=True, exist_ok=True)

            cmd = runner_cmd or ["agy", "--dangerously-skip-permissions", "-p", prompt]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(bdir)
            )
            out = (result.stdout or "") + (result.stderr or "")

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
            if "completed_fingerprints" not in checkpoint:
                checkpoint["completed_fingerprints"] = []
            checkpoint["completed_fingerprints"].append(fp)

            if not out_file.exists():
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(out)

        except subprocess.TimeoutExpired:
            task["status"] = "TIMEOUT"
            task["error"] = f"Task timed out after {timeout}s"
        except Exception as e:
            task["status"] = "FAILED"
            task["error"] = str(e)

        save_json(q_path, queue)
        save_json(cp_path, checkpoint)
        processed_count += 1

    return processed_count


def main():
    lock_path = os.environ.get("MUSE_LOCK_FILE", str(DEFAULT_LOCK_FILE))
    lock_fd = is_another_instance_running(lock_path)
    if not lock_fd:
        print("Another Muse runner is active. Exiting.")
        sys.exit(0)

    try:
        run_muse_cycle()
    finally:
        release_lock(lock_fd)


if __name__ == "__main__":
    main()
