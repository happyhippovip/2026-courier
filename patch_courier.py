with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

# Fix 1: Make goal_satisfied NOT True by default
content = content.replace(
    '"acceptance_evidence": {"goal_satisfied": payload.get("test_returncode") == 0 or payload.get("verdict") == "PASS"}',
    '"acceptance_evidence": {"goal_satisfied": payload.get("goal_satisfied") is True, "tests_passed": payload.get("test_returncode") == 0 or payload.get("verdict") == "PASS"}'
)

# Fix 2: If task_type == "VERIFICATION", spawn a new DISCOVERY task instead of returning []
verification_block = """
        elif task_type == "VERIFICATION":
            ev = last_result.get("acceptance_evidence", {})
            if ev.get("tests_passed") is True:
                # Tests passed for the last increment. Do another discovery to see if we're done or need more increments.
                return [{
                    "goal": goal_text,
                    "normalized_task": "Analyze repo state to identify improvements.",
                    "capability_required": "local repo analysis",
                    "preferred_agent": "GEMINI",
                    "is_heavy": True,
                    "requires_write": False,
                    "task": {
                        "action": "discover_improvement_opportunities",
                        "goal_context": goal_text,
                        "capability_request": "local repo analysis"
                    }
                }]
            else:
                # Tests failed, we should probably stop or repair, but returning [] stops the loop
                return []
"""

content = content.replace('        return []\n\n    def evaluate_success', verification_block + '\n        return []\n\n    def evaluate_success')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
