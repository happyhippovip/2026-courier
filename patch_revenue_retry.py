import os

with open("scripts/revenue_worker_adapter.py", "r") as f:
    c = f.read()

retry_loop = """
                    write_log("Posting result...")
                    import random
                    post_backoff = 2
                    while True:
                        res, err = http_post(config, "/tasks/result", res_payload)
                        if err:
                            write_log(f"Result post failed: {err}. Retrying in {post_backoff}s...")
                            time.sleep(post_backoff + random.uniform(0, 2))
                            post_backoff = min(60, post_backoff * 2)
                        else:
                            write_log(f"Task {task_id} completed and posted successfully.")
                            break
"""

c = c.replace("""                    write_log("Posting result...")\n                    http_post(config, "/tasks/result", res_payload)\n                    write_log(f"Task {task_id} completed.")""", retry_loop)

with open("scripts/revenue_worker_adapter.py", "w") as f:
    f.write(c)

