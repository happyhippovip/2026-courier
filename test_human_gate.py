from scripts.courier_safety_dispatcher import CourierSafetyDispatcher

def check(mission, task):
    return CourierSafetyDispatcher._requires_human_gate(mission, task)

# SAFE cases
assert not check({}, {"target_files": ["tests/test_login.py"]}), "Failed SAFE 1"
assert not check({}, {"changed_files": ["tests/test_deploy.py", "tests/test_publication.py"]}), "Failed SAFE 2"

# UNSAFE cases
assert check({}, {"action": "deploy application"}), "Failed UNSAFE 1"
assert check({}, {"action": "login to external service"}), "Failed UNSAFE 2"

print("TARGETED_SAFETY_CLASSIFICATION_TESTS: PASS")
