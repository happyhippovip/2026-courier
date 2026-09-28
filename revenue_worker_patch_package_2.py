import os
import sys

def apply_patch():
    path = "scripts/revenue_worker_adapter.py"
    if not os.path.exists(path):
        print(f"{path} not found")
        sys.exit(1)
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    old_block = """                except subprocess.CalledProcessError as e:
                    write_log(f"Task execution failed: {e.output.decode('utf-8', errors='ignore')}")
                    # Could implement fail endpoint here if one existed"""
                    
    new_block = """                except subprocess.CalledProcessError as e:
                    write_log(f"Task execution failed: {e.output.decode('utf-8', errors='ignore')}")
                    res_payload = {
                        "goal_id": task.get("goal_id", "unknown"),
                        "task_id": task_id,
                        "attempt_id": attempt_id,
                        "dispatch_id": task.get("dispatch_id", "unknown"),
                        "worker_id": worker_id,
                        "run_id": f"run-{uuid.uuid4().hex[:8]}",
                        "result_id": f"result-{uuid.uuid4().hex[:8]}",
                        "status": "FAILED",
                        "artifacts": [],
                        "stderr": e.output.decode('utf-8', errors='ignore')
                    }
                    write_log("Posting FAILED result...")
                    http_post(config, "/tasks/result", res_payload)"""
                    
    if old_block not in content:
        if "Posting FAILED result" in content:
            print("Patch already applied.")
            return
        print("Could not find the target block to patch.")
        sys.exit(1)
        
    patched = content.replace(old_block, new_block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patch successfully applied to revenue_worker_adapter.py (error handling)")

if __name__ == "__main__":
    apply_patch()
