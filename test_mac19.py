import urllib.request, json
url = "http://127.0.0.1:8080/goals"
headers = {"Content-Type": "application/json", "Authorization": "Bearer 321606503a874d39b50f6137e3321b7f"}
data = {
    "goal_text": "Customer Hello World Setup",
    "workflow_plan": [
        {
            "task_id": "CREATE_DIR",
            "target_agent": "mac",
            "instruction": "mkdir -p /tmp/courier_customer_test && echo 'Created'",
            "exclusive_resources": ["CUSTOMER_TEST"]
        },
        {
            "task_id": "WRITE_INDEX",
            "target_agent": "mac",
            "instruction": "echo '<h1>Welcome</h1>' > /tmp/courier_customer_test/index.html && echo 'Written'",
            "depends_on": ["CREATE_DIR"],
            "exclusive_resources": ["CUSTOMER_TEST"]
        },
        {
            "task_id": "VERIFY_OUTPUT",
            "target_agent": "mac",
            "instruction": "cat /tmp/courier_customer_test/index.html",
            "depends_on": ["WRITE_INDEX"],
            "exclusive_resources": ["CUSTOMER_TEST"]
        }
    ]
}
req = urllib.request.Request(url, headers=headers, data=json.dumps(data).encode("utf-8"))
with urllib.request.urlopen(req) as response:
    goal_id = json.loads(response.read().decode())["goal_id"]
    print("Submitted:", goal_id)
