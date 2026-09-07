import requests
import json
import uuid

URL_CHAOS = "http://127.0.0.1:8080/api/founder/chaos"
URL_REVIEW = "http://127.0.0.1:8080/api/founder/review"

def fail_test(accept_payload, name, payload_mod, expected_status=400):
    mod = dict(accept_payload)
    mod.update(payload_mod)
    r = requests.post(URL_REVIEW, json=mod)
    assert r.status_code == expected_status, f"Negative [{name}] failed. Expected {expected_status}, got {r.status_code}: {r.text}"
    print(f"PASS: Negative [{name}]")

def test_identity_and_review_gates():
    print("Running Gate Regression Tests...")
    
    # 1. Setup identity chain
    raw_chaos = "Goal: Acceptance Test Identity Chain"
    resp = requests.post(URL_CHAOS, json={
        "raw_chaos": raw_chaos,
        "title": "Gate Regression",
        "correlation_id": "CORR-REGRESSION-1"
    })
    data = resp.json()
    dossier_id = data["dossier"]["dossier_id"]
    correlation_id = data["dossier"]["correlation_id"]
    goal_id = data["submitted_goal_ids"][0]
    
    import os
    from scripts.courier_safety_dispatcher import MissionQueue, canonical_hash
    workspace = os.getcwd()
    queue = MissionQueue(workspace)
    mission_id = str(uuid.uuid4())
    queue.enqueue({
        "mission_id": mission_id,
        "goal": goal_id,
        "normalized_task": "Regression Task",
        "capability_required": "repo verification",
        "preferred_agent": "CLI1",
        "requires_write": False,
        "is_heavy": False,
        "status": "PENDING",
        "task": {"action": "verify_improvement_tests"}
    })
    
    queue.transition(mission_id, "CLAIMED", claimed_by="CLI1")
    queue.transition(mission_id, "RUNNING", claimed_by="CLI1")
    
    result_fp = canonical_hash({"verdict": "PASS"})
    queue.transition(mission_id, "PENDING_VERIFY", claimed_by="CLI1", result_reference=result_fp, task_hash=result_fp)
    
    accept_payload = {
        "dossier_id": dossier_id,
        "goal_id": goal_id,
        "mission_id": mission_id,
        "correlation_id": correlation_id,
        "result_fingerprint": result_fp,
        "verification_reference": "dummy",
        "action": "ACCEPT"
    }
    
    fail_test(accept_payload, "ACCEPT before VERIFIED", {}, 400)
    
    verification_ref = canonical_hash({"verified": True})
    queue.transition(mission_id, "VERIFIED", claimed_by="CLI1", verification_reference=verification_ref)
    accept_payload["verification_reference"] = verification_ref
    
    fail_test(accept_payload, "missing dossier", {"dossier_id": None})
    fail_test(accept_payload, "wrong dossier", {"dossier_id": "WRONG"})
    fail_test(accept_payload, "wrong goal", {"goal_id": "WRONG"})
    fail_test(accept_payload, "wrong mission", {"mission_id": "WRONG"})
    fail_test(accept_payload, "wrong correlation", {"correlation_id": "WRONG"})
    fail_test(accept_payload, "missing fingerprint", {"result_fingerprint": None})
    fail_test(accept_payload, "wrong fingerprint", {"result_fingerprint": "WRONG"})
    fail_test(accept_payload, "missing verification_reference", {"verification_reference": None})
    fail_test(accept_payload, "wrong verification_reference", {"verification_reference": "WRONG"})
    
    resp2 = requests.post(URL_CHAOS, json={"raw_chaos": "Foreign", "title": "Foreign"})
    foreign_goal_id = resp2.json()["submitted_goal_ids"][0]
    fail_test(accept_payload, "foreign goal mission", {"goal_id": foreign_goal_id})
    
    # REJECT testing
    reject_payload = dict(accept_payload)
    reject_payload["action"] = "REJECT"
    r = requests.post(URL_REVIEW, json=reject_payload)
    assert r.status_code == 200
    
    goals = json.loads(open("events/founder-mode/goals.json").read())
    active_goal = next(g for g in goals if g["goal_id"] == goal_id)
    assert active_goal["status"] == "FAILED"
    
    print("All Gate Regression Tests completed.")

if __name__ == "__main__":
    test_identity_and_review_gates()
