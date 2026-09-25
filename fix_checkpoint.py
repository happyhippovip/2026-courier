import re
with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

replacement = """
        checkpoint_files = [
            REPO_ROOT / "scripts" / "mac_worker" / "state" / "current_task.json",
            REPO_ROOT / "scripts" / "mac_worker" / "state_2" / "current_task.json"
        ]
        checkpoint_found = False
        checkpoint_content = None
        for _ in range(20):
            for cp in checkpoint_files:
                if cp.exists():
                    import json
                    try:
                        data = json.loads(cp.read_text())
                        if data.get("task_id") == task_seq1:
                            checkpoint_found = True
                            checkpoint_content = data
                            break
                    except Exception:
                        pass
            if checkpoint_found:
                break
            time.sleep(0.1)

        assert checkpoint_found, "Checkpoint file current_task.json was not created on disk before completion"
        assert checkpoint_content["task_id"] == task_seq1
"""

c = re.sub(
    r"        checkpoint_file = REPO_ROOT / \"scripts\".*?assert checkpoint_content\[\"task_id\"\] == task_seq1",
    replacement.strip(),
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)
