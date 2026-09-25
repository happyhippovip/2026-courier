"""Contract test: revenue intake payload must match POST /goals server contract.

The server only honors goal_text + workflow_plan; a "tasks" key is silently
ignored, which used to drop the audit step on the floor (lost result).
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.revenue_customer_intake import build_intake_payload, submit_intake


def test_payload_uses_workflow_plan_not_tasks():
    payload = build_intake_payload("o", "r", "sha123", "cust-1")
    assert "workflow_plan" in payload
    assert "tasks" not in payload
    assert isinstance(payload["goal_text"], str) and payload["goal_text"].strip()


def test_audit_step_carries_binding_and_instruction():
    payload = build_intake_payload("o", "r", "sha123", "cust-1")
    (step,) = payload["workflow_plan"]
    assert step["task_id"].startswith("REV-")
    assert "instruction" in step and "sha123" in step["instruction"]
    assert step["target_owner"] == "o"
    assert step["target_repo"] == "r"
    assert step["target_sha"] == "sha123"
    assert step["customer_reference"] == "cust-1"
    assert "revenue_safety_audit" in step["capabilities"]


def test_submit_posts_workflow_plan(capsys):
    captured = {}

    class FakeRequests:
        def post(self, url, json=None, headers=None):
            captured["payload"] = json
            return types.SimpleNamespace(status_code=200, text="ok")

    import scripts.revenue_customer_intake as ric

    real, ric.requests = ric.requests, FakeRequests()
    try:
        submit_intake("o", "r", "sha123", "cust-1")
    finally:
        ric.requests = real
    assert "workflow_plan" in captured["payload"]
    assert "Success!" in capsys.readouterr().out
