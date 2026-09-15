import re
with open("scripts/run_live_production_goal.py", "r") as f:
    code = f.read()

# Add registration of WINDOWS before evaluate_next_safe_work
registration_code = """
    # Register WINDOWS worker
    from scripts.live_worker_registry import LiveWorkerRegistry, AvailabilityClass, WorkerState
    reg = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    record = reg.register_worker("WINDOWS", "WINDOWS_NATIVE", "WINDOWS", AvailabilityClass.TEMPORARY_24_HOUR, [r"C:\\Dev\\Windows-AI-OS"])
    record.state = WorkerState.AVAILABLE.value
    reg._save_worker_record(record)
    
"""

code = code.replace("    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)", registration_code + "    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)")

with open("scripts/run_live_production_goal.py", "w") as f:
    f.write(code)
