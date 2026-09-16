import os
with open("scripts/revenue_worker_adapter.py", "r") as f:
    c = f.read()

c = c.replace("while True:", "error_backoff = 2\n    while True:")

c = c.replace("""        except Exception as e:
            write_log(f"Error in main loop: {traceback.format_exc()}")
            
        time.sleep(config["POLL_INTERVAL_SECONDS"])""", """        except Exception as e:
            write_log(f"Error in main loop: {traceback.format_exc()}")
            import random
            time.sleep(error_backoff + random.uniform(0, 2))
            error_backoff = min(60, error_backoff * 2)
            continue
            
        import random
        time.sleep(config["POLL_INTERVAL_SECONDS"] + random.uniform(0, 1))
        error_backoff = 2""")

with open("scripts/revenue_worker_adapter.py", "w") as f:
    f.write(c)

