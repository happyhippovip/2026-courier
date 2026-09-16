import os
with open("scripts/github_worker_adapter.py", "r") as f:
    c = f.read()

post_result_code = """
def post_result(result: dict[str, Any]) -> None:
    api_key = os.environ.get("COURIER_API_KEY")
    if not api_key:
        raise RuntimeError("COURIER_API_KEY is required to post a DurableResult")
    url = os.environ.get("COURIER_SERVER", "http://127.0.0.1:8080").rstrip("/") + "/tasks/result"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    import random
    post_backoff = 2
    while True:
        try:
            response = requests.post(url, json=result, headers=headers, timeout=15)
            if response.status_code < 400:
                print(f"RESULT_POSTED_TO_COURIER=YES status={response.status_code}", flush=True)
                return
            if response.status_code not in TRANSIENT_HTTP_STATUSES:
                raise RuntimeError(f"result POST failed: {response.status_code} {response.text}")
        except requests.RequestException as exc:
            print(f"result POST failed: {exc}. Retrying in {post_backoff}s...")
        time.sleep(post_backoff + random.uniform(0, 2))
        post_backoff = min(60, post_backoff * 2)
"""

import re
c = re.sub(r'def post_result\(result: dict\[str, Any\]\) -> None:.*?def run\(task_file_name: str\) -> int:', post_result_code + '\n\ndef run(task_file_name: str) -> int:', c, flags=re.DOTALL)

with open("scripts/github_worker_adapter.py", "w") as f:
    f.write(c)

