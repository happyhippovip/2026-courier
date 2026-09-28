import re

content = open("scripts/mac_worker/daemon.py").read()

# Patch 1: run_native heartbeat
content = content.replace(
    '        stdout, stderr = proc.communicate(timeout=600)\n',
    '''        import threading
        stop_heartbeat = threading.Event()
        def hb():
            while not stop_heartbeat.wait(30.0):
                try:
                    http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
                except Exception:
                    pass
        hb_thread = threading.Thread(target=hb, daemon=True)
        hb_thread.start()
        try:
            stdout, stderr = proc.communicate(timeout=600)
        finally:
            stop_heartbeat.set()
'''
)

# Patch 2: run_agy heartbeat
content = content.replace(
    '        stdout, stderr = process.communicate(timeout=300)\n',
    '''        import threading
        stop_heartbeat = threading.Event()
        def hb():
            while not stop_heartbeat.wait(30.0):
                try:
                    http_post(config, "/workers/heartbeat", {"worker_id": config["WORKER_ID"]})
                except Exception:
                    pass
        hb_thread = threading.Thread(target=hb, daemon=True)
        hb_thread.start()
        try:
            stdout, stderr = process.communicate(timeout=300)
        finally:
            stop_heartbeat.set()
'''
)

# Patch 3: upload rejection
content = content.replace(
'''            if task:
                outcome = upload_pending_artifacts(config, task, current_task_state_file) if upload_enabled(config) else "READY"
                if outcome == "READY":
                    outcome = deliver_result(config, task["result_payload"])
                if outcome == "UNDELIVERED":''',
'''            if task:
                upload_outcome = upload_pending_artifacts(config, task, current_task_state_file) if upload_enabled(config) else "READY"
                if upload_outcome == "REJECTED":
                    task["result_payload"]["status"] = "FAILED"
                    task["result_payload"]["stderr"] = task["result_payload"].get("stderr", "") + "\\nArtifact upload permanently rejected (e.g. size/binding error)."
                    task["result_payload"]["artifacts"] = []
                    persist_task(current_task_state_file, task)
                    write_log(f"Result for task {task['task_id']} upload REJECTED; converting to FAILED result.")
                    upload_outcome = "READY"
                    
                outcome = upload_outcome
                if outcome == "READY":
                    outcome = deliver_result(config, task["result_payload"])
                
                if outcome == "UNDELIVERED":'''
)

with open("mac_worker_patch_package.py", "w") as f:
    f.write(open(__file__).read())
