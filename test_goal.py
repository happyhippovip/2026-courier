import urllib.request, json
try:
    print(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8111/goals', data=json.dumps({'goal_text': 'test', 'workflow_plan': [{'task_id': 'T1', 'target_agent': 'macos', 'instruction': 'echo hi'}]}).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer test-secret'})).read().decode())
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.reason, e.read().decode())
