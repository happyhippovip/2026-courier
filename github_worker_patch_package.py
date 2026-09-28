import sys
import os

def apply_patch():
    path = "scripts/github_worker_adapter.py"
    if not os.path.exists(path):
        print("github_worker_adapter.py not found")
        sys.exit(1)
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    new_except_block = """    except (IndexError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"GITHUB_WORKER_ERROR={exc}", file=sys.stderr)
        try:
            task_file = Path(sys.argv[1])
            if task_file.is_file():
                task = json.loads(task_file.read_text(encoding="utf-8"))
                err_result = {
                    "goal_id": task.get("goal_id", "unknown"),
                    "task_id": task.get("task_id", "unknown"),
                    "attempt_id": task.get("attempt_id", "unknown"),
                    "dispatch_id": task.get("dispatch_id", "unknown"),
                    "worker_id": task.get("worker_id", "unknown"),
                    "run_id": "failed",
                    "result_id": f"result-{task.get('dispatch_id', 'err')}",
                    "status": "FAILED",
                    "artifacts": [],
                    "stderr": str(exc)
                }
                post_result(err_result)
                write_state(task_file, {"dispatch_id": task.get("dispatch_id", ""), "status": "POSTED_FAILED"})
        except Exception as inner_exc:
            print(f"Failed to post error result: {inner_exc}", file=sys.stderr)
        raise SystemExit(1)"""

    if "POSTED_FAILED" in content:
        print("Patch already applied.")
        return

    old_except_block = """    except (IndexError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"GITHUB_WORKER_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)"""
        
    if old_except_block not in content:
        print("Could not find the target block to patch.")
        sys.exit(1)
        
    patched = content.replace(old_except_block, new_except_block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patch successfully applied to github_worker_adapter.py")

if __name__ == "__main__":
    apply_patch()
