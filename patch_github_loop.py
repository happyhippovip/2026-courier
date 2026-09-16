import os
with open("scripts/courier_github_dispatcher.py", "r") as f:
    c = f.read()

# Add error_backoff
c = c.replace("while True:", "error_backoff = 2\n    while True:")

# Replace time.sleep(5)
c = c.replace("""        except Exception as e:
            log(f"Error polling for tasks: {e}")
            
        time.sleep(5)""", """        except Exception as e:
            log(f"Error polling for tasks: {e}")
            import random
            time.sleep(error_backoff + random.uniform(0, 2))
            error_backoff = min(60, error_backoff * 2)
            continue
            
        import random
        time.sleep(5 + random.uniform(0, 1))
        error_backoff = 2""")

with open("scripts/courier_github_dispatcher.py", "w") as f:
    f.write(c)

