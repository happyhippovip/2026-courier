import os
import json
import urllib.request
import urllib.error

# Load config or use default
API_URL = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080")
try:
    import keyring
    API_KEY = os.environ.get("COURIER_API_KEY") or keyring.get_password("courier_worker", "courier_api_key")
except ImportError:
    API_KEY = os.environ.get("COURIER_API_KEY")

def get_status():
    if not API_KEY:
        return "COURIER ERROR | Missing API Key"
        
    req = urllib.request.Request(f"{API_URL}/status", method="GET")
    req.add_header("Authorization", f"Bearer {API_KEY}")
    
    try:
        res = urllib.request.urlopen(req, timeout=5)
        data = json.loads(res.read().decode('utf-8'))
    except Exception as e:
        return f"COURIER OFFLINE | {e}"
        
    req_workers = urllib.request.Request(f"{API_URL}/workers", method="GET")
    req_workers.add_header("Authorization", f"Bearer {API_KEY}")
    try:
        w_res = urllib.request.urlopen(req_workers, timeout=5)
        workers = json.loads(w_res.read().decode('utf-8'))
    except Exception:
        workers = {}
        
    status_str = "COURIER OK | SERVER OK"
    
    if workers:
        for w_id, w in workers.items():
            state = "idle" if w.get("available") else "busy"
            cap = w.get("platform", "worker").upper()
            status_str += f" | {cap} {state}"
    else:
        status_str += " | NO WORKERS"
        
    return status_str

if __name__ == "__main__":
    print(get_status())
