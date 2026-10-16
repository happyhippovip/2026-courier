import sys
content = open("tests/test_win_clean_machine_harness.py", "r").read()

search = """
        worker_pid = None
        for p in claims_dir.glob("dispatch-*.json"):
            try:
                record = json.loads(p.read_text())
                if record.get("task_id") == blocked_id:
                    worker_pid = record["owner_pid"]
                    break
            except Exception:
                pass
        
        
        if worker_pid is None:
            print(f"Claims dir {claims_dir} contents: {list(claims_dir.glob('*'))}")
            print(f"Looking for task_id: {blocked_id}")
            for p in claims_dir.glob("dispatch-*.json"):
                print(f"File {p.name}: {p.read_text()}")
        
        assert worker_pid is not None, "Could not find worker_pid from claims"
"""

replace = """
        worker_pid = None
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < 10:
            for p in claims_dir.glob("dispatch-*.json"):
                try:
                    record = json.loads(p.read_text())
                    if record.get("task_id") == blocked_id:
                        worker_pid = record["owner_pid"]
                        break
                except Exception:
                    pass
            if worker_pid is not None:
                break
            time.sleep(0.5)
        
        if worker_pid is None:
            print(f"Claims dir {claims_dir} contents: {list(claims_dir.glob('*'))}")
            print(f"Looking for task_id: {blocked_id}")
            for p in claims_dir.glob("dispatch-*.json"):
                try:
                    print(f"File {p.name}: {p.read_text()}")
                except Exception as e:
                    print(f"File {p.name} read error: {e}")
        
        assert worker_pid is not None, "Could not find worker_pid from claims"
"""

if search in content:
    content = content.replace(search, replace)
    open("tests/test_win_clean_machine_harness.py", "w").write(content)
    print("Success")
else:
    print("Search block not found")
