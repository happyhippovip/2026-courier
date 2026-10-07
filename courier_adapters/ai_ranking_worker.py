import os
import sys
import json
import time
import requests
from pathlib import Path

def evaluate_and_route(hub_url, token, worker_id):
    headers = {"X-Courier-Token": token}
    print(f"Starting Phase 4 AI Ranking worker {worker_id}")
    
    while True:
        try:
            requests.post(f"{hub_url}/v1/heartbeat", json={"worker_id": worker_id}, headers=headers)
            
            res = requests.post(f"{hub_url}/v1/claim", json={"worker_id": worker_id}, headers=headers)
            if res.status_code == 204:
                time.sleep(2)
                continue
                
            if res.ok:
                data = res.json()
                task = data.get("task") or data
                if task and "task_id" in task:
                    spec = task.get("spec", {})
                    adapter = spec.get("adapter")
                    
                    if adapter == "ai_ranking_worker":
                        start_res = requests.post(f"{hub_url}/v1/start", json={"dispatch_id": task["dispatch_id"], "worker_id": worker_id}, headers=headers)
                        if not start_res.ok:
                            continue
                            
                        params = spec.get("params", {})
                        title = params.get("title", "").lower()
                        content = params.get("content_text", "").lower()
                        
                        # Local rules first:
                        # Reject empty content or spam
                        if not title or not content:
                            requests.post(f"{hub_url}/v1/result", json={
                                "dispatch_id": task["dispatch_id"],
                                "result_id": f"res-invalid",
                                "outcome": "failure",
                                "artifacts": [],
                                "reason": "Empty content"
                            }, headers=headers)
                            continue
                            
                        # Simple rule: highly relevant crypto keywords
                        keywords = ["bitcoin", "btc", "ethereum", "eth", "solana", "sec", "regulation"]
                        score = sum(1 for kw in keywords if kw in title or kw in content)
                        
                        if score > 0:
                            # Route to delivery (Telegram)
                            delivery_task = {
                                "adapter": "telegram_delivery",
                                "effect_class": "idempotent",
                                "max_attempts": 3,
                                "lease_ttl_s": 60,
                                "params": params,
                                "idempotency_key": f"telegram:{params.get('article_id')}"
                            }
                            route_res = requests.post(f"{hub_url}/v1/tasks", json=delivery_task, headers=headers)
                            
                            requests.post(f"{hub_url}/v1/result", json={
                                "dispatch_id": task["dispatch_id"],
                                "result_id": f"res-{params.get('article_id')}",
                                "outcome": "success",
                                "artifacts": [],
                            }, headers=headers)
                        else:
                            # Not relevant enough, drop it
                            requests.post(f"{hub_url}/v1/result", json={
                                "dispatch_id": task["dispatch_id"],
                                "result_id": f"res-{params.get('article_id')}",
                                "outcome": "success", # Successfully processed and dropped
                                "artifacts": [],
                                "reason": "Dropped due to low score"
                            }, headers=headers)
                    else:
                        time.sleep(1)
        except Exception as e:
            print(f"Ranking loop error: {e}")
            
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
            
    evaluate_and_route(hub_url, token, "ai-ranking-worker-1")
