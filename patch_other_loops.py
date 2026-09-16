import os

def refine_loop(filename, base_sleep):
    with open(filename, "r") as f:
        c = f.read()

    if "import random" not in c:
        c = c.replace("import time", "import time\nimport random")

    c = c.replace("while True:", "error_backoff = 2\n    while True:")

    c = c.replace(f"""        except Exception as e:
            log(f"Error polling for tasks: {{e}}")
            
        time.sleep({base_sleep})""", f"""        except Exception as e:
            log(f"Error polling for tasks: {{e}}")
            import random
            time.sleep(error_backoff + random.uniform(0, 2))
            error_backoff = min(60, error_backoff * 2)
            continue
            
        import random
        time.sleep({base_sleep} + random.uniform(0, 1))
        error_backoff = 2""")

    # Same for watchdog
    c = c.replace(f"""        except Exception as e:
            log(f"Error calling watchdog endpoint: {{e}}")
            
        time.sleep({base_sleep})""", f"""        except Exception as e:
            log(f"Error calling watchdog endpoint: {{e}}")
            import random
            time.sleep(error_backoff + random.uniform(0, 2))
            error_backoff = min(60, error_backoff * 2)
            continue
            
        import random
        time.sleep({base_sleep} + random.uniform(0, 1))
        error_backoff = 2""")

    with open(filename, "w") as f:
        f.write(c)

refine_loop("scripts/courier_verifier.py", 5)
refine_loop("scripts/courier_watchdog.py", 60)
