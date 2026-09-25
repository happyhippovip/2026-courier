import re
from pathlib import Path

# 1. Fix daemon.py
p_daemon = Path("scripts/windows_worker/daemon.py")
daemon_code = p_daemon.read_text()

helper = """
def generate_result_id(res):
    identity = {
        "goal_id": res.get("goal_id"),
        "task_id": res.get("task_id"),
        "attempt_id": res.get("attempt_id"),
        "dispatch_id": res.get("dispatch_id"),
        "execution_ref": res.get("execution_ref"),
        "worker_id": res.get("worker_id"),
        "run_id": res.get("run_id"),
        "status": res.get("status"),
        "artifacts": res.get("artifacts", []),
        "runtime_identity": res.get("runtime_identity")
    }
    if "batch_id" in res:
        identity["batch_id"] = res["batch_id"]
    if "prompt_id" in res:
        identity["prompt_id"] = res["prompt_id"]
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return "result-" + hashlib.sha256(encoded).hexdigest()

"""

if "def generate_result_id" not in daemon_code:
    daemon_code = daemon_code.replace("def run_task(task, config):", helper + "def run_task(task, config):")

# Find all places returning res_json in run_task
daemon_code = re.sub(
    r'(\s+)return res_json',
    r'\1res_json["result_id"] = generate_result_id(res_json)\1return res_json',
    daemon_code
)

# And for the crash marker res_json
daemon_code = re.sub(
    r'(\s+)if "batch_id" in crashed_task:\s*res_json\["batch_id"\] = crashed_task\["batch_id"\]',
    r'\1if "batch_id" in crashed_task: res_json["batch_id"] = crashed_task["batch_id"]\1res_json["result_id"] = generate_result_id(res_json)',
    daemon_code
)

p_daemon.write_text(daemon_code)

# 2. Fix test_windows_runtime_torture.py
p_test = Path("tests/test_windows_runtime_torture.py")
test_code = p_test.read_text()

test_helper = """
def generate_result_id(res):
    identity = {
        "goal_id": res.get("goal_id"),
        "task_id": res.get("task_id"),
        "attempt_id": res.get("attempt_id"),
        "dispatch_id": res.get("dispatch_id"),
        "execution_ref": res.get("execution_ref"),
        "worker_id": res.get("worker_id"),
        "run_id": res.get("run_id"),
        "status": res.get("status"),
        "artifacts": res.get("artifacts", []),
        "runtime_identity": res.get("runtime_identity")
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode('utf-8')
    import hashlib
    return "result-" + hashlib.sha256(encoded).hexdigest()

"""

if "def generate_result_id" not in test_code:
    test_code = test_code.replace("def test_windows_torture():", test_helper + "def test_windows_torture():")

test_code = re.sub(
    r'"result_id": f"result-\{uuid\.uuid4\(\)\.hex\}",',
    r'"result_id": "WILL_BE_REPLACED",',
    test_code
)

test_code = re.sub(
    r'(\s+)with open\(result_marker, "w"\) as f:',
    r'\1fake_result["result_id"] = generate_result_id(fake_result)\1with open(result_marker, "w") as f:',
    test_code
)

p_test.write_text(test_code)

