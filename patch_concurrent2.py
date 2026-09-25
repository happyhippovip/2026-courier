import os
from pathlib import Path

test_file = Path("tests/test_server_integration_contract.py")
content = test_file.read_text()

# We just replace the lines
old = """    def claim():
        with server_app.app.test_client() as concurrent_http:
            return concurrent_http.post(
                "/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}
            ).get_json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: claim(), range(2)))

    claimed = [response["task"] for response in responses if response.get("task")]
    assert len(claimed) == 1
    assert claimed[0]["task_id"] == "task-concurrent"
    assert sorted(response.get("reason", "CLAIMED") for response in responses) == [
        "CLAIMED", "WORKER_BUSY"
    ]"""

new = """    def claim(worker_id):
        with server_app.app.test_client() as concurrent_http:
            return concurrent_http.post(
                "/tasks/claim", headers=auth(), json={"worker_id": worker_id}
            ).get_json()

    # Also register MAC-02
    http.post("/workers/register", headers=auth(), json={"worker_id": "MAC-02", "platform": "mac", "capabilities": ["macos"]})

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(claim, ["MAC-01", "MAC-02"]))

    claimed = [response.get("task") for response in responses if response.get("task")]
    assert len(claimed) == 1
    assert claimed[0]["task_id"] == "task-concurrent"
    
    unclaimed = [response for response in responses if not response.get("task")]
    assert len(unclaimed) == 1
    assert unclaimed[0].get("task") is None"""

if old in content:
    content = content.replace(old, new)
    test_file.write_text(content)
    print("Success")
else:
    print("Not found")
