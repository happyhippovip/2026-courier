import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").absolute()))
import agent_handoff_ledger as ahl
import tempfile
import datetime

# Dummy resolver for the mock URL
def dummy_resolver(url):
    print(f"DEBUG: dummy_resolver called with {url}")
    return {
        "verdict": "PASS",
        "producer_principal": "github-actions",
        "verifier_principal": "sigstore-verifier",
        "result_sha256": "dummy-hash",
        "goal_id": "test-goal",
        "binding": {
            "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "runtime": "mac-1"
        }
    }

ahl._attestation_resolver = dummy_resolver
ahl._verify_attestation = dummy_resolver

def base_record():
    return {
        "PROJECT": "courier",
        "GOAL": "test-goal",
        "BRANCH": "release-candidate-integration",
        "CURRENT_SHA": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "RUNTIME_IDENTITY": "mac-1",
        "RUNTIME_OWNER": "test-owner",
        "STATUS": "READY",
        "PROVEN_EDGES": [],
        "UNPROVEN_EDGES": [],
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "BLOCKER_OWNER": "NONE",
        "NEXT_EXECUTABLE_ACTION": "DO_WORK",
        "ACTIVE_WRITERS": ["session-a"],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 1,
        "TASKS_COMPLETED": 2,
        "WORKERS_USED": 1,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "LAST_EVIDENCE": [],
        "LAST_UPDATED_BY": "writer",
        "CONTINUATION_CHECKPOINT": "NONE",
        "QUEUE_INDEPENDENT": "YES",
        "CLEAN_IDLE": "NO"
    }

def base_guard(observed_at):
    return {
        "flow": [
            "EXECUTION",
            "EVIDENCE",
            "ACCEPTANCE_GUARD",
            "LEDGER_TRANSITION",
            "NEXT_EXECUTABLE_ACTION"
        ],
        "transition_state": "READY",
        "binding": {
            "branch": "release-candidate-integration",
            "current_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "runtime_identity": "mac-1"
        },
        "worker_state": "ACTIVE",
        "acceptance_predicate": {
            "name": "COURIER_NATIVE",
            "version": "1.0",
            "required_results": ["RUNTIME_ARTIFACT"],
            "results": {
                "RUNTIME_ARTIFACT": {
                    "status": "UNKNOWN",
                    "observed_value": "PENDING",
                    "evidence_urls": []
                }
            }
        },
        "evidence": [{
            "source_url": "https://github.com/example/project/actions/runs/12345",
            "source_type": "MACHINE_ARTIFACT",
            "observed_at": observed_at,
            "evidence_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "runtime_binding": "mac-1",
            "validity": "VALID",
            "reason": "artifact",
            "producer_id": "github-actions",
            "verifier_id": "sigstore-verifier",
            "result_sha256": "dummy-hash"
        }]
    }

tmp = Path(tempfile.mkdtemp())
path = tmp / "ledger.json"

fresh_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
rec = base_record()
ahl.initialize(path, rec, base_guard(fresh_time), 5.0)

g1 = base_guard(fresh_time)
g1["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
    "status": "PASS", "observed_value": "BOUND",
    "evidence_urls": ["https://github.com/example/project/actions/runs/12345"],
}

# Instead of blindly updating, let's inject a print into ahl module to see what goes wrong.
code = """
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
"""
exec(code, ahl.__dict__)

b1 = ahl.update(path, 0, {"TASKS_COMPLETED": 1}, "stale-writer", 5.0, g1)
print("b1 transition:", b1["acceptance_guard"]["transition_state"])

b2 = ahl.update(path, 1, {"TASKS_COMPLETED": 2}, "independent-verifier", 5.0)
print("b2 transition:", b2["acceptance_guard"]["transition_state"])

