import requests
import time
import os
import sys
import traceback
from pathlib import Path

def deliver(hub_url, token, worker_id, tel_token, tel_chat_id):
    headers = {"X-Courier-Token": token}
    
    print(f"Starting telegram delivery worker {worker_id} for chat {tel_chat_id}")
    
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
                    task_id = task["task_id"]
                    spec = task.get("spec", {})
                    adapter = spec.get("adapter")
                    
                    if adapter == "telegram_delivery":
                        start_res = requests.post(f"{hub_url}/v1/start", json={"dispatch_id": task["dispatch_id"], "worker_id": worker_id}, headers=headers)
                        if not start_res.ok:
                            print(f"Failed to start {task_id}: {start_res.text}")
                            continue

                        params = spec.get("params", {})
                        article_id = params.get("article_id")
                        title = params.get("title", "No Title")
                        author = params.get("author") or "Unknown"
                        date = params.get("published_at", "")
                        content = params.get("content_text", "")
                        url = params.get("url", "")
                        
                        if article_id:
                            message = f"*{title}*\nBy {author} on {date}\n\n{content}\n\n{url}"
                            if len(message) > 4000:
                                message = message[:4000] + "... (truncated)"
                            
                            tel_url = f"https://api.telegram.org/bot{tel_token}/sendMessage"
                            tel_res = requests.post(tel_url, json={
                                "chat_id": tel_chat_id,
                                "text": message,
                                "parse_mode": "Markdown"
                            }, timeout=10)
                            
                            if tel_res.ok:
                                print(f"Delivered {article_id} to Telegram")
                                res2 = requests.post(f"{hub_url}/v1/result", json={
                                    "dispatch_id": task["dispatch_id"],
                                    "result_id": f"res-{article_id}",
                                    "outcome": "success",
                                    "artifacts": []
                                }, headers=headers)
                                if not res2.ok:
                                    print(f"Error reporting success: {res2.text}")
                            else:
                                print(f"Failed to deliver {article_id}: {tel_res.status_code} {tel_res.text}")
                                reason = f"telegram_{tel_res.status_code}"
                                res2 = requests.post(f"{hub_url}/v1/result", json={
                                    "dispatch_id": task["dispatch_id"],
                                    "result_id": f"res-{article_id}-fail",
                                    "outcome": "failure",
                                    "artifacts": [],
                                    "reason": reason[:64]
                                }, headers=headers)
                                if not res2.ok:
                                    print(f"Error reporting failure: {res2.text}")
                        else:
                            requests.post(f"{hub_url}/v1/result", json={
                                "dispatch_id": task["dispatch_id"],
                                "result_id": f"res-invalid",
                                "outcome": "failure",
                                "artifacts": [],
                                "reason": "missing article_id"
                            }, headers=headers)
                    else:
                        time.sleep(1)
            else:
                print(f"Claim error: {res.status_code} {res.text}")
        except Exception as e:
            print(f"Delivery loop error: {e}")
            traceback.print_exc()
            
        time.sleep(2)

if __name__ == '__main__':
    tel_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tel_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not tel_token or not tel_chat_id:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in the environment.")
        sys.exit(1)

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
            
    deliver(hub_url, token, "telegram-delivery-worker-1", tel_token, tel_chat_id)
