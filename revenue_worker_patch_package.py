import os
import sys

def apply_patch():
    path = "scripts/revenue_worker_adapter.py"
    if not os.path.exists(path):
        print(f"{path} not found")
        sys.exit(1)
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # We need to replace the artifact packaging and result posting logic
    old_block = """                    import hashlib
                    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
                    artifact_b64 = base64.b64encode(artifact_bytes).decode('utf-8')
                    
                    # Post result
                    res_payload = {
                        "task_id": task_id,
                        "attempt_id": attempt_id,
                        "worker_id": worker_id,
                        "result_data": result_data,
                        "artifact_name": "revenue_artifacts.zip",
                        "artifact_sha256": artifact_sha,
                        "artifact_content_base64": artifact_b64
                    }
                    
                    write_log("Posting result...")
                    http_post(config, "/tasks/result", res_payload)"""
                    
    new_block = """                    import hashlib
                    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
                    
                    # Upload artifact using /artifacts endpoint
                    meta = {
                        "name": "revenue_artifacts.zip",
                        "sha256": artifact_sha,
                        "size": len(artifact_bytes),
                        "goal_id": task.get("goal_id", "unknown"),
                        "task_id": task_id,
                        "attempt_id": attempt_id,
                        "dispatch_id": task.get("dispatch_id", "unknown"),
                        "worker_id": worker_id
                    }
                    
                    import urllib.request, json
                    req = urllib.request.Request(f"{config['COURIER_SERVER']}/artifacts", method="POST")
                    req.add_header("Authorization", f"Bearer {config['COURIER_API_KEY']}")
                    req.add_header("Content-Type", "application/octet-stream")
                    req.add_header("X-Courier-Artifact", json.dumps(meta))
                    req.data = artifact_bytes
                    
                    try:
                        with urllib.request.urlopen(req) as response:
                            art_resp = json.loads(response.read().decode("utf-8"))
                    except Exception as e:
                        write_log(f"Artifact upload failed: {e}")
                        art_resp = {}
                        
                    # Prepare DurableResult
                    res_payload = {
                        "goal_id": task.get("goal_id", "unknown"),
                        "task_id": task_id,
                        "attempt_id": attempt_id,
                        "dispatch_id": task.get("dispatch_id", "unknown"),
                        "worker_id": worker_id,
                        "run_id": f"run-{uuid.uuid4().hex[:8]}",
                        "result_id": f"result-{uuid.uuid4().hex[:8]}",
                        "status": "SUCCESS",
                        "artifacts": [
                            {
                                "path": "revenue_artifacts.zip",
                                "sha256": artifact_sha,
                                "size": len(artifact_bytes),
                                "artifact_id": art_resp.get("artifact_id", "unknown")
                            }
                        ]
                    }
                    
                    write_log("Posting result...")
                    http_post(config, "/tasks/result", res_payload)"""
                    
    if old_block not in content:
        if "X-Courier-Artifact" in content:
            print("Patch already applied.")
            return
        print("Could not find the target block to patch.")
        sys.exit(1)
        
    patched = content.replace(old_block, new_block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patch successfully applied to revenue_worker_adapter.py")

if __name__ == "__main__":
    apply_patch()
