import re
with open("scripts/run_live_production_goal.py", "r") as f:
    code = f.read()

code = code.replace(
    'record = reg.register_worker("WINDOWS", "WINDOWS_NATIVE", "WINDOWS", AvailabilityClass.TEMPORARY_30_DAY, [r"C:\\Dev\\Windows-AI-OS"])',
    'record = reg.register_worker(worker_id="WINDOWS", role="WINDOWS_NATIVE", provider="WINDOWS", availability_class=AvailabilityClass.TEMPORARY_30_DAY, mutable_scope=[r"C:\\Dev\\Windows-AI-OS"])'
)

with open("scripts/run_live_production_goal.py", "w") as f:
    f.write(code)
