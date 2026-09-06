with open("tests/test_write_reliability.py", "r") as f:
    content = f.read()

# Fix mock returns in test_e10 and test_e11
content = content.replace(
    'return {"result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "payload": {"verdict": "PASS"}}}',
    'return {"dispatched_to": agent, "result_path": "dummy.json", "ack_path": "a.json", "envelope_path": "e.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "payload": {"verdict": "PASS"}}}'
)
content = content.replace(
    'return {"result": {"status": "HUMAN_GATE", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "payload": {"verdict": "HUMAN_GATE"}, "error_type": "AUTHENTICATION_REQUIRED"}}',
    'return {"dispatched_to": agent, "result_path": "dummy.json", "ack_path": "a.json", "envelope_path": "e.json", "route": agent, "result": {"status": "HUMAN_GATE", "task_hash": env.task_hash, "mission_id": env.mission_id, "target_agent": agent, "payload": {"verdict": "HUMAN_GATE"}, "error_type": "AUTHENTICATION_REQUIRED"}}'
)
content = content.replace(
    'return {"result": {"status": "COMPLETED", "task_hash": "WRONG_HASH", "mission_id": env.mission_id, "target_agent": agent, "payload": {"verdict": "PASS"}}}',
    'return {"dispatched_to": agent, "result_path": "dummy.json", "ack_path": "a.json", "envelope_path": "e.json", "route": agent, "result": {"status": "COMPLETED", "task_hash": "WRONG_HASH", "mission_id": env.mission_id, "target_agent": agent, "payload": {"verdict": "PASS"}}}'
)

# Fix E18 ledger check
content = content.replace(
    'history = self.dispatcher.ledger.read_history()\n        reviews = [r for r in history if r.get("event") == "REVIEW_RECORDED"]\n        self.assertTrue(len(reviews) > 0)\n        last_review = reviews[-1]',
    'ledger_data = self.dispatcher.ledger._load_ledger()\n        reviews = ledger_data.get("reviews", {})\n        self.assertTrue(len(reviews) > 0)\n        last_review = list(reviews.values())[-1]'
)

with open("tests/test_write_reliability.py", "w") as f:
    f.write(content)
