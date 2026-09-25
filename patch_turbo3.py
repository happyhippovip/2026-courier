import re
with open("tests/test_turbo_queue_concurrency.py", "r") as f:
    content = f.read()

content = content.replace('exec_times = {}', 'exec_times = {}\n        thread_res_ids = {}')
content = content.replace('completion_events[tid].set()', 'thread_res_ids[tid] = result["result_id"]\n                    completion_events[tid].set()')
content = re.sub(r'state = server\.app\.load_state\(\)\n.*?for tid in', 'state = server.app.load_state()\n    for tid in', content, flags=re.DOTALL)
content = content.replace('res_ids[tid]', 'thread_res_ids[tid]')
content = content.replace('res_ids["A"]', 'thread_res_ids["A"]')

with open("tests/test_turbo_queue_concurrency.py", "w") as f:
    f.write(content)
