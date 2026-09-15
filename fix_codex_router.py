with open("scripts/router_dispatch_codex.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "from scripts.opportunity_queue import OpportunityQueue, Opportunity" in line:
        new_lines.append("from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState\n")
    if "from pathlib import Path" in line and "reg = LiveWorkerRegistry" in lines[min(i+1, len(lines)-1)]:
        pass # Skip
    new_lines.append(line)

with open("scripts/router_dispatch_codex.py", "w") as f:
    f.writelines(new_lines)
