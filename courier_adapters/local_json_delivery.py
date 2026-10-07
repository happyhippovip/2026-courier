import requests
import json
import time
import os
import sys
from pathlib import Path

def deliver(hub_url, token, worker_id):
    out_dir = Path("delivered_articles")
    out_dir.mkdir(exist_ok=True)
    
    headers = {"X-Courier-Token": token}
    
    while True:
        try:
            # Heartbeat
            requests.post(f"{hub_url}/v1/heartbeat", json={"worker_id": worker_id}, headers=headers)
            
            # Claim task
            res = requests.post(f"{hub_url}/v1/claim", json={"worker_id": worker_id}, headers=headers)
            if res.ok:
                data = res.json()
                task = data.get("task") or data
                if task and "task_id" in task:
                    task_id = task["task_id"]
                    spec = task.get("spec", {})
                    adapter = spec.get("adapter")
                    
                    if adapter == "local_json_delivery":
                        params = spec.get("params", {})
                        article_id = params.get("article_id")
                        if article_id:
                            out_file = out_dir / f"{article_id}.json"
                            with open(out_file, "w", encoding="utf-8") as f:
                                json.dump(params, f, indent=2)
                            print(f"Delivered {article_id} to {out_file}")
                            
                            # Report success
                            requests.post(f"{hub_url}/v1/result", json={
                                "worker_id": worker_id,
                                "task_id": task_id,
                                "dispatch_id": task["dispatch_id"],
                                "attempt": task["attempt"],
                                "result_id": f"res-{article_id}",
                                "status": "SUCCESS",
                                "artifacts": [{"path": str(out_file), "sha256": "0" * 64}],
                                "raw_result": {"delivered": True}
                            }, headers=headers)
                        else:
                            # Reject invalid
                            requests.post(f"{hub_url}/v1/result", json={
                                "worker_id": worker_id,
                                "task_id": task_id,
                                "dispatch_id": task["dispatch_id"],
                                "attempt": task["attempt"],
                                "result_id": f"res-invalid",
                                "status": "FAILED",
                                "artifacts": [],
                                "raw_result": {"error": "missing article_id"}
                            }, headers=headers)
                    else:
                        # Yield back if wrong adapter (though we registered for generic, in a real system we'd route)
                        time.sleep(1)
        except Exception as e:
            print(f"Delivery loop error: {e}")
            
        time.sleep(2)

if __name__ == '__main__':
    hub_url = os.environ.get("COURIER_HUB_URL", "http://127.0.0.1:8080")
    token = os.environ.get("COURIER_HUB_TOKEN")
    if not token:
        home_env = os.environ.get("COURIER_HOME")
        if home_env:
            base = Path(home_env)
        else:
            pd = os.environ.get("LOCALAPPDATA")
            base = (Path(pd) if pd else Path.home() / ".courier") / "Courier"
            
        token_path = base / "run" / "controller.token"
        if token_path.exists():
            token = token_path.read_text().strip()
        else:
            print("No token found")
            sys.exit(1)
            
    deliver(hub_url, token, "local-delivery-worker-1")
