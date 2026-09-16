import os
with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

atomic_write = """
                    temp_task_file = str(current_task_state_file) + ".tmp"
                    with open(temp_task_file, 'w') as f:
                        json.dump(task, f)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp_task_file, current_task_state_file)
"""

c = c.replace("""
                    with open(current_task_state_file, 'w') as f:
                        json.dump(task, f)
""", atomic_write)

# Also fix the task_crash_count file to be atomic
crash_write = """
        with open(str(task_crash_file) + ".tmp", "w") as f:
            json.dump(crash_counts, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(task_crash_file) + ".tmp", task_crash_file)
"""
c = c.replace("""
        with open(task_crash_file, "w") as f:
            json.dump(crash_counts, f)
""", crash_write)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)

