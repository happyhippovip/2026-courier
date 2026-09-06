import json

with open('events/mission-queue/queue.json') as f:
    q = json.load(f)

m = [x for x in q['missions'] if x['status'] == 'HUMAN_GATE'][-1]
task = m['task']
for k, v in task.items():
    if k not in ("files", "target_files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):
        if "test_deploy" in str(v) or "tests/test_" in str(v):
            print(f"FOUND IN KEY {k}")
