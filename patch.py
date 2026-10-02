with open('tests/test_server_app_uncovered.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('"task_id": "t1", "status"', '"task_id": "t1", "goal_id": "g1", "status"')
text = text.replace('"task_id": "t1"}', '"task_id": "t1", "goal_id": "g1"}')
text = text.replace('{"task_id": "t1", "worker_id": "w1"}', '{"task_id": "t1", "worker_id": "w1", "goal_id": "g1"}')
text = text.replace('{"task_id": "t1", "result_id": "r1"}', '{"task_id": "t1", "result_id": "r1", "goal_id": "g1"}')
text = text.replace('{"task_id": "t1", "result_id": "r2"}', '{"task_id": "t1", "result_id": "r2", "goal_id": "g1"}')
text = text.replace('{"task_id": "t1"}', '{"task_id": "t1", "goal_id": "g1"}')
with open('tests/test_server_app_uncovered.py', 'w', encoding='utf-8') as f:
    f.write(text)
