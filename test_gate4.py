import json
import re

with open('events/mission-queue/queue.json') as f:
    q = json.load(f)

m = [x for x in q['missions'] if x['status'] == 'HUMAN_GATE'][-1]
task = m['task']
task_parts = []
for k, v in task.items():
    if k not in ("files", "target_files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):
        task_parts.append(str(v))

raw_text = " ".join(str(x) for x in (m.get("goal", ""), m.get("normalized_task", ""), " ".join(task_parts)))
print("RAW TEXT:")
print(raw_text)
