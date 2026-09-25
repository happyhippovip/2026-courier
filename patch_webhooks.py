import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

webhook_func = """
def _trigger_webhooks(state, goal):
    import threading, json, urllib.request
    community_id = goal.get("community_id", "public")
    webhooks = state.get("communities", {}).get(community_id, {}).get("webhooks", [])
    if not webhooks:
        return
        
    payload = json.dumps({"goal_id": goal["goal_id"], "status": "DONE"}).encode("utf-8")
    
    def post_webhook(url):
        try:
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5.0)
        except Exception as e:
            print(f"Webhook failed for {url}: {e}")
            
    for w in webhooks:
        threading.Thread(target=post_webhook, args=(w,), daemon=True).start()

"""

# Insert _trigger_webhooks before def verify_task()
target_func = '@app.route("/tasks/verify", methods=["POST"])'
content = content.replace(target_func, webhook_func + target_func)

# Replace goal["status"] = "DONE"
content = content.replace('goal["status"] = "DONE"', 'goal["status"] = "DONE"\n                    _trigger_webhooks(state, goal)')

p.write_text(content)
print("SUCCESS")
