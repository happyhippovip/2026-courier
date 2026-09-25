import requests
import time
import uuid

SERVER_URL = "http://127.0.0.1:8080"
API_KEY = "321606503a874d39b50f6137e3321b7f"
headers = {"Authorization": f"Bearer {API_KEY}"}

def wait_for_done(goal_id):
    start = time.time()
    while time.time() - start < 120:
        res = requests.get(f"{SERVER_URL}/goals/{goal_id}", headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "DONE":
                print(f"Goal {goal_id} reached DONE state!")
                return True
        time.sleep(1)
    print("Goal timed out!")
    return False

if __name__ == "__main__":
    if wait_for_done("ACCEPTANCE-PROOF-3c3fc404"):
        print("ACCEPTANCE PROOF SUCCESS")
    else:
        print("ACCEPTANCE PROOF FAILED")
