import json

with open('events/mission-queue/queue.json') as f:
    q = json.load(f)

m = [x for x in q['missions'] if x['status'] == 'HUMAN_GATE'][-1]
g = m.get("goal", "")
if "test_deploy" in g or "tests/test_" in g: print("IN GOAL")
n = m.get("normalized_task", "")
if "test_deploy" in n or "tests/test_" in n: print("IN NORMALIZED TASK")
