import json

with open('events/mission-queue/queue.json') as f:
    q = json.load(f)

for m in q['missions']:
    if m['status'] == 'HUMAN_GATE' and m['task']['action'] == 'verify_improvement_tests':
        task = m['task']
        for k, v in task.items():
            if k not in ("files", "target_files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):
                print(f"Key: {k}, Value length: {len(str(v))}")
                if "test_deploy" in str(v) or "tests/test_" in str(v):
                    print(f"  -> MATCHED LIST IN {k}!")
