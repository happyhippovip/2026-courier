import os
from pathlib import Path

test_file = Path("tests/test_server_integration_contract.py")
content = test_file.read_text()

# Modify the concurrent claim test to use TWO different workers.
old = """    def test_concurrent_claims_have_exactly_one_winner(tmp_path, monkeypatch):
        http = client(tmp_path, monkeypatch)
        assert http.post(
            "/workers/register",
            headers=auth(),
            json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]},
        ).status_code == 200
        assert http.post"""

new = """    def test_concurrent_claims_have_exactly_one_winner(tmp_path, monkeypatch):
        http = client(tmp_path, monkeypatch)
        assert http.post(
            "/workers/register",
            headers=auth(),
            json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]},
        ).status_code == 200
        assert http.post(
            "/workers/register",
            headers=auth(),
            json={"worker_id": "MAC-02", "platform": "mac", "capabilities": ["macos"]},
        ).status_code == 200
        assert http.post"""

content = content.replace(old, new)

old_claim = """        def claim():
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

new_claim = """        def claim(worker_id):
            with server_app.app.test_client() as concurrent_http:
                return concurrent_http.post(
                    "/tasks/claim", headers=auth(), json={"worker_id": worker_id}
                ).get_json()
    
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(claim, ["MAC-01", "MAC-02"]))
    
        claimed = [response["task"] for response in responses if response.get("task")]
        assert len(claimed) == 1
        assert claimed[0]["task_id"] == "task-concurrent"
        # The loser gets {"task": None} because there are no other tasks in the queue.
        # It won't get WORKER_BUSY because the loser is a DIFFERENT worker and has no task.
        assert sorted(response.get("reason", "CLAIMED") for response in responses) == [
            "CLAIMED", "CLAIMED" # Actually wait, if the queue is empty, the server just returns {"task": None} with no reason
        ]"""
# wait, if queue is empty, it just returns {"task": None} without reason.

# Let's fix the assertion:
new_claim2 = """        def claim(worker_id):
            with server_app.app.test_client() as concurrent_http:
                return concurrent_http.post(
                    "/tasks/claim", headers=auth(), json={"worker_id": worker_id}
                ).get_json()
    
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(claim, ["MAC-01", "MAC-02"]))
    
        claimed = [response.get("task") for response in responses if response.get("task")]
        assert len(claimed) == 1
        assert claimed[0]["task_id"] == "task-concurrent"
        
        # the loser gets {"task": None}, with no reason field (since it just scanned the empty queue)
        unclaimed = [response for response in responses if not response.get("task")]
        assert len(unclaimed) == 1
        assert unclaimed[0] == {"task": None}"""

content = content.replace(old_claim, new_claim2)
test_file.write_text(content)
