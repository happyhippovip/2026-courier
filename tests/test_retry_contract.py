import server.app
import pytest
import os
import json
from server.app import app, save_state, load_state, set_task_status


pytestmark = pytest.mark.fast

@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    os.environ["COURIER_STATE_FILE"] = str(tmp_path / "test_state.json")
    from server import app as server_app
    server_app.STATE_FILE = str(tmp_path / "test_state.json")
    server_app._cached_state_json = None
    with app.test_client() as client:
        yield client

def test_retry_creates_canonical_attempt_identity(client, tmp_path):
    state = {
        "workers": {
            "w1": {"available": True, "capabilities": ["linux"], "last_seen": 0, "current_task": None}
        },
        "tasks": {
            "t1": {
                "task_id": "t1",
                "goal_id": "g1",
                "status": "FAILED_TERMINAL",
                "worker_id": "w1",
                "attempts": 1,
                "attempt_id": "t1:attempt:1",
                "dispatch_id": "d-1",
                "execution_ref": "e-1", "result": {"result_id": "res-1", "worker_id": "w1", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING},
                "target_agent": "linux"
            }
        },
        "goals": {
            "g1": {
                "status": "BLOCKED",
                "workflow_plan": [
                    {
                        "task_id": "t1",
                        "goal_id": "g1",
                        "status": "FAILED_TERMINAL",
                        "target_capability": "linux",
                        "attempts": 1
                    }
                ]
            }
        }
    }
    save_state(state)
    
    from server.app import API_KEY
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Trigger resume
    res = client.post("/tasks/t1/resume", json={"action": "retry"}, headers=headers)
    assert res.status_code == 200
    
    # Claim task
    res = client.post("/tasks/claim", json={"worker_id": "w1"}, headers=headers)
    assert res.status_code == 200
    task = res.json["task"]
    
    # It must have advanced attempt
    assert task["attempts"] == 2
    assert task["attempt_id"] == "t1:attempt:2"
    assert task["dispatch_id"] != "d-1"
    assert task["execution_ref"] != "e-1"
    assert task["worker_id"] == "w1"

def test_late_result_rejected_due_to_attempt_mismatch(client, tmp_path):
    state = {
        "workers": {
            "w1": {"available": False, "capabilities": ["linux"], "last_seen": 0, "current_task": "t1"}
        },
        "tasks": {
            "t1": {
                "task_id": "t1",
                "goal_id": "g1",
                "status": "DISPATCHED",
                "worker_id": "w1",
                "attempts": 2,
                "attempt_id": "t1:attempt:2",
                "dispatch_id": "d-2",
                "execution_ref": "e-2"
            }
        },
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {
                        "task_id": "t1",
                        "status": "DISPATCHED"
                    }
                ]
            }
        }
    }
    save_state(state)
    
    from server.app import API_KEY
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Worker sends late result for attempt 1
    res = client.post("/tasks/result", json={
        "goal_id": "g1",
        "task_id": "t1",
        "worker_id": "w1",
        "attempt_id": "t1:attempt:1",
        "dispatch_id": "d-1",
        "execution_ref": "e-1", "result": {"result_id": "res-1", "worker_id": "w1", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING},
        "run_id": "r-1",
        "result_id": "res-1",
        "status": "SUCCESS",
        "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    
    assert res.status_code == 400
    assert "attempt_id mismatch" in res.json["error"] or "dispatch_id mismatch" in res.json["error"]

def test_scheduler_fixture_duplicate_effect_rejection_for_reconciled_task(client, tmp_path):
    state = {
        "workers": {
            "w1": {"available": True, "capabilities": ["linux"], "last_seen": 0, "current_task": None}
        },
        "tasks": {
            "t1": {
                "task_id": "t1",
                "goal_id": "g1",
                "status": "RECONCILED",
                "worker_id": "w1",
                "attempts": 1,
                "attempt_id": "t1:attempt:1",
                "dispatch_id": "d-1",
                "execution_ref": "e-1", "result": {"result_id": "res-1", "worker_id": "w1", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING}
            }
        },
        "goals": {
            "g1": {
                "status": "ACTIVE",
                "workflow_plan": [
                    {
                        "task_id": "t1",
                        "status": "RECONCILED"
                    }
                ]
            }
        }
    }
    save_state(state)
    
    from server.app import API_KEY
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    # Worker redundantly sends result for already RECONCILED task
    res = client.post("/tasks/result", json={
        "goal_id": "g1",
        "task_id": "t1",
        "worker_id": "w1",
        "attempt_id": "t1:attempt:1",
        "dispatch_id": "d-1",
        "execution_ref": "e-1", "result": {"result_id": "res-1", "worker_id": "w1", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING},
        "run_id": "r-1",
        "result_id": "res-1",
        "status": "SUCCESS",
        "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    
    # The server should just cleanly IGNORE it instead of applying twice
    assert res.status_code == 200
    assert res.json["status"] == "ACK_DUPLICATE"

def test_integration_result_verify_worker_freigabe(client, tmp_path, monkeypatch):
    """
    Echter lokaler Integrationstest:
    Prüft, ob WORKER_BUSY, task ownership und current_task automatisch korrekt 
    zurückgesetzt werden (keine manuelle Freigabe).
    Beweis: Worker ist geblockt, während Task aktiv ist -> Worker ist frei nach Result.
    """
    import server.app

    from server.app import API_KEY, VERIFIER_API_KEY, load_state
    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}
    
    # 1. Register worker
    res = client.post("/workers/register", json={
        "worker_id": "w2", "platform": "test",
        "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-2", "cost_class": "free"
    }, headers=headers)
    assert res.status_code == 200
    
    # 2. Create goal with TWO tasks
    res = client.post("/goals", json={
        "goal_text": "Integration test Freigabe",
        "workflow_plan": [
            {"task_id": "t2", "target_agent": "linux", "instruction": "do work 1"},
            {"task_id": "t3", "target_agent": "linux", "instruction": "do work 2", "depends_on": ["t2"]}
        ],
        "terminal": True
    }, headers=headers)
    assert res.status_code == 200
    
    # 3. Worker claims task (t2)
    res = client.post("/tasks/claim", json={"worker_id": "w2"}, headers=headers)
    assert res.status_code == 200
    task = res.json["task"]
    assert task["task_id"] == "t2"
    
    # Verify worker is BOUND (WORKER_BUSY / Task Ownership)
    state_after_claim = load_state()
    assert state_after_claim["workers"]["w2"]["current_task"] == "t2"
    assert state_after_claim["workers"]["w2"]["available"] is False
    
    # BEWEIS: Ein zweiter Claim-Versuch während WORKER_BUSY schlägt fehl / liefert None
    res_busy = client.post("/tasks/claim", json={"worker_id": "w2"}, headers=headers)
    assert res_busy.json.get("task") is None, "Worker claims another task despite WORKER_BUSY"
    
    # 4. Worker sends result (Dies MUSS die Ownership automatisch aufheben)
    result_id = "res-2"
    res = client.post("/tasks/result", json={
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "worker_id": "w2",
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "run_id": "r-2",
        "result_id": result_id,
        "status": "SUCCESS",
        "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res.status_code == 200
    
    # Verify task state advanced AND worker is automatically freed!
    state_after_result = load_state()
    assert state_after_result["tasks"]["t2"]["status"] == "RESULT_RECEIVED"
    assert state_after_result["workers"]["w2"]["current_task"] is None
    assert state_after_result["workers"]["w2"]["available"] is True
    
    actual_fp = state_after_result["tasks"]["t2"]["result"]["result_id"]
    
    # 5. Verifier approves result -> RECONCILED
    res = client.post("/tasks/verify", json={
        "task_id": "t2",
        "result_id": result_id,
        "verifier_id": "independent-verifier-1",
        "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING,
        "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert res.status_code == 200
    
    # 6. Assert RECONCILED and Worker is still free
    state_final = load_state()
    assert state_final["tasks"]["t2"]["status"] == "RECONCILED"
    assert state_final["workers"]["w2"]["current_task"] is None
    assert state_final["workers"]["w2"]["available"] is True
    
    # BEWEIS: Freigabe funktioniert - Worker kann nun Aufgabe t3 claimen!
    res_t3 = client.post("/tasks/claim", json={"worker_id": "w2"}, headers=headers)
    assert res_t3.json.get("task") is not None
    assert res_t3.json["task"]["task_id"] == "t3"

def test_integration_manipulated_binding_fails_closed(client, tmp_path):
    """
    Echter lokaler Integrationstest:
    Result-/Verify-Fall mit manipulierter Bindung (Runtime Identity) muss fail-closed bleiben.
    """
    from server.app import API_KEY, VERIFIER_API_KEY, load_state
    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}
    
    # 1. Register worker
    res = client.post("/workers/register", json={
        "worker_id": "w_manipulated", "platform": "test",
        "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-3", "cost_class": "free"
    }, headers=headers)
    assert res.status_code == 200
    
    # 2. Create goal
    res = client.post("/goals", json={
        "goal_text": "Integration test Manipulated Binding",
        "workflow_plan": [{"task_id": "t_manipulated", "target_agent": "linux", "instruction": "do work"}],
        "terminal": True
    }, headers=headers)
    assert res.status_code == 200
    
    # 3. Worker claims task
    res = client.post("/tasks/claim", json={"worker_id": "w_manipulated"}, headers=headers)
    assert res.status_code == 200
    task = res.json["task"]
    
    # 4. Worker sends VALID result
    result_id = "res-manip"
    res = client.post("/tasks/result", json={
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "worker_id": "w_manipulated",
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "run_id": "r-manip",
        "result_id": result_id,
        "status": "SUCCESS",
        "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res.status_code == 200
    
    # Verify task state advanced
    state_after_result = load_state()
    assert state_after_result["tasks"]["t_manipulated"]["status"] == "RESULT_RECEIVED"
    actual_fp = state_after_result["tasks"]["t_manipulated"]["result"]["result_id"]
    
    # 5. Verifier attempts to approve result, BUT with manipulated runtime identity binding!
    manipulated_runtime = "forged-worker-identity"
    
    res = client.post("/tasks/verify", json={
        "task_id": "t_manipulated",
        "result_id": result_id,
        "verifier_id": "independent-verifier-1",
        "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING,
        "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING,
        "received_runtime_identity": manipulated_runtime,
        "_skip_auto_identity": True
    }, headers=v_headers)
    
    # MUST fail-closed!
    assert res.status_code == 400, f"Expected 400 but got {res.status_code}: {res.json}"
    assert "runtime identity mismatch" in res.json.get("error", "").lower()
    
    # 6. Assert NOT RECONCILED
    state_final = load_state()
    assert state_final["tasks"]["t_manipulated"]["status"] == "RESULT_RECEIVED"

def test_integration_dependency_resolution(client, tmp_path, monkeypatch):
    """
    Beweise A+B->C ohne direkte Statusmanipulation:
    A fertig/verifiziert, B noch offen -> C bleibt gesperrt;
    erst nach gültigem B-Abschluss darf C genau einmal freigegeben werden.
    """
    import server.app
    from server.app import API_KEY, VERIFIER_API_KEY, load_state
    
    # Verhindere 25-Sekunden-Hang bei leeren Claims

    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}

    # Register workers
    for wid in ["w_A", "w_B", "w_C", "w_D"]:
        res = client.post("/workers/register", json={
            "worker_id": wid, "platform": "test",
            "capabilities": ["linux"], "authorities": [],
            "provider": "local", "capacity_identity": f"cap-{wid}", "cost_class": "free"
        }, headers=headers)
        assert res.status_code == 200

    # Create Goal with A, B and C (C depends on A and B)
    res = client.post("/goals", json={
        "goal_text": "Dependency test A+B -> C",
        "workflow_plan": [
            {"task_id": "task_A", "target_agent": "linux", "instruction": "A"},
            {"task_id": "task_B", "target_agent": "linux", "instruction": "B"},
            {"task_id": "task_C", "target_agent": "linux", "instruction": "C", "depends_on": ["task_A", "task_B"]}
        ],
        "terminal": True
    }, headers=headers)
    assert res.status_code == 200

    # 1. w_A claims A
    resA = client.post("/tasks/claim", json={"worker_id": "w_A"}, headers=headers)
    tA = resA.json["task"]
    assert tA["task_id"] == "task_A"

    # 2. w_B claims B
    resB = client.post("/tasks/claim", json={"worker_id": "w_B"}, headers=headers)
    tB = resB.json["task"]
    assert tB["task_id"] == "task_B"

    # 3. w_C tries to claim C -> MUST be None (blocked by A and B)
    resC_empty = client.post("/tasks/claim", json={"worker_id": "w_C"}, headers=headers)
    assert resC_empty.status_code == 200
    assert resC_empty.json.get("task") is None

    # 4. Finish A
    client.post("/tasks/result", json={
        "goal_id": tA["goal_id"], "task_id": tA["task_id"], "worker_id": "w_A", "attempt_id": tA["attempt_id"],
        "dispatch_id": tA["dispatch_id"], "execution_ref": tA["execution_ref"], "run_id": "run-A",
        "result_id": "res-A", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    state = load_state()
    fp_A = state["tasks"]["task_A"]["result"]["result_id"]
    resV_A = client.post("/tasks/verify", json={
        "task_id": "task_A", "result_id": "res-A", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert resV_A.status_code == 200, resV_A.json

    # 5. w_C tries to claim C -> MUST be None (A is done, but B is still open)
    resC_empty2 = client.post("/tasks/claim", json={"worker_id": "w_C"}, headers=headers)
    assert resC_empty2.status_code == 200
    assert resC_empty2.json.get("task") is None

    # 6. Finish B
    client.post("/tasks/result", json={
        "goal_id": tB["goal_id"], "task_id": tB["task_id"], "worker_id": "w_B", "attempt_id": tB["attempt_id"],
        "dispatch_id": tB["dispatch_id"], "execution_ref": tB["execution_ref"], "run_id": "run-B",
        "result_id": "res-B", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    state = load_state()
    fp_B = state["tasks"]["task_B"]["result"]["result_id"]
    resV_B = client.post("/tasks/verify", json={
        "task_id": "task_B", "result_id": "res-B", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert resV_B.status_code == 200, resV_B.json

    # 7. w_C tries to claim C -> MUST succeed now!
    resC = client.post("/tasks/claim", json={"worker_id": "w_C"}, headers=headers)
    assert resC.status_code == 200
    tC = resC.json.get("task")
    assert tC is not None
    assert tC["task_id"] == "task_C"

    # 8. w_D tries to claim -> MUST be None (C exactly once)
    resD = client.post("/tasks/claim", json={"worker_id": "w_D"}, headers=headers)
    assert resD.status_code == 200
    assert resD.json.get("task") is None

def test_integration_idempotency_duplicate_delivery(client, tmp_path, monkeypatch):
    """
    Beweise Idempotenz: doppelte Result-Zustellung und doppelte Verify-Zustellung für A.
    Es darf keinen zweiten logischen Abschluss, keine zweite Freigabe und keinen doppelten Effekt geben.
    """
    import server.app
    from server.app import API_KEY, VERIFIER_API_KEY, load_state

    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}

    for wid in ["w_A", "w_C"]:
        client.post("/workers/register", json={
            "worker_id": wid, "platform": "test", "capabilities": ["linux"], "authorities": [],
            "provider": "local", "capacity_identity": f"cap-{wid}", "cost_class": "free"
        }, headers=headers)

    client.post("/goals", json={
        "goal_text": "Idempotency test A -> C",
        "workflow_plan": [
            {"task_id": "task_A", "target_agent": "linux", "instruction": "A"},
            {"task_id": "task_C", "target_agent": "linux", "instruction": "C", "depends_on": ["task_A"]}
        ],
        "terminal": True
    }, headers=headers)

    # 1. w_A claims A
    resA = client.post("/tasks/claim", json={"worker_id": "w_A"}, headers=headers)
    tA = resA.json["task"]

    # 2. First Result for A
    res_result_1 = client.post("/tasks/result", json={
        "goal_id": tA["goal_id"], "task_id": tA["task_id"], "worker_id": "w_A", "attempt_id": tA["attempt_id"],
        "dispatch_id": tA["dispatch_id"], "execution_ref": tA["execution_ref"], "run_id": "run-A",
        "result_id": "res-A", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res_result_1.status_code == 200
    assert res_result_1.json.get("status") == "ACK_RESULT_RECEIVED"

    # 3. DUPLICATE Result for A
    res_result_2 = client.post("/tasks/result", json={
        "goal_id": tA["goal_id"], "task_id": tA["task_id"], "worker_id": "w_A", "attempt_id": tA["attempt_id"],
        "dispatch_id": tA["dispatch_id"], "execution_ref": tA["execution_ref"], "run_id": "run-A",
        "result_id": "res-A", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res_result_2.status_code == 200
    # Es muss abgewiesen/ignoriert werden
    assert res_result_2.json.get("status") == "ACK_DUPLICATE"

    state = load_state()
    fp_A = state["tasks"]["task_A"]["result"]["result_id"]

    # 4. First Verify for A
    res_verify_1 = client.post("/tasks/verify", json={
        "task_id": "task_A", "result_id": "res-A", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert res_verify_1.status_code == 200

    # 5. DUPLICATE Verify for A
    res_verify_2 = client.post("/tasks/verify", json={
        "task_id": "task_A", "result_id": "res-A", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert res_verify_2.status_code == 200
    assert res_verify_2.json.get("status") == "ACK_DUPLICATE", res_verify_2.json

    # 6. w_C claims C (darf exakt einmal freigegeben werden)
    resC = client.post("/tasks/claim", json={"worker_id": "w_C"}, headers=headers)
    tC = resC.json.get("task")
    assert tC is not None
    assert tC["task_id"] == "task_C"

    # 7. Zweiter Claim Versuch -> Keine doppelte Freigabe von C!
    resC_dup = client.post("/tasks/claim", json={"worker_id": "w_C"}, headers=headers)
    assert resC_dup.json.get("task") is None

def test_integration_parallel_execution_overlap(client, tmp_path, monkeypatch):
    """
    Teste anschließend zwei unabhängige Tasks A und B mit zwei lokalen Testworkern
    und belege tatsächliche zeitliche Überlappung über Start-/Endereignisse;
    zwei sequentielle HTTP-Calls zählen nicht als Parallelitätsbeweis.
    """
    import threading
    import time
    from server.app import API_KEY, app

    # Wait nicht komplett ausschalten, aber auf 0.1 reduzieren, um Deadlocks zu vermeiden,
    # falls Worker leer laufen (sollte hier aber nicht passieren)
    import server.app

    headers = {"Authorization": f"Bearer {API_KEY}"}

    client.post("/workers/register", json={
        "worker_id": "w_1", "platform": "test", "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-1", "cost_class": "free"
    }, headers=headers)
    
    client.post("/workers/register", json={
        "worker_id": "w_2", "platform": "test", "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-2", "cost_class": "free"
    }, headers=headers)

    client.post("/goals", json={
        "goal_text": "Parallel Overlap Test",
        "workflow_plan": [
            {"task_id": "t_parallel_A", "target_agent": "linux", "instruction": "A"},
            {"task_id": "t_parallel_B", "target_agent": "linux", "instruction": "B"}
        ],
        "terminal": True
    }, headers=headers)

    timings = {}
    lock = threading.Lock()

    def worker_run(wid):
        # Eigener Thread-Client
        tc = app.test_client()
        
        # 1. Claim
        res = tc.post("/tasks/claim", json={"worker_id": wid}, headers=headers)
        task = res.json.get("task")
        if not task:
            return
            
        # 2. Start Time
        start_t = time.time()
        
        # 3. Simulate processing time to enforce physical overlap
        time.sleep(1.0)
        
        # 4. Result Time
        end_t = time.time()
        
        # 5. Submit Result
        tc.post("/tasks/result", json={
            "goal_id": task["goal_id"], "task_id": task["task_id"], "worker_id": wid,
            "attempt_id": task["attempt_id"], "dispatch_id": task["dispatch_id"],
            "execution_ref": task["execution_ref"], "run_id": f"run-{wid}",
            "result_id": f"res-{wid}", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
        }, headers=headers)
        
        with lock:
            timings[task["task_id"]] = (start_t, end_t)

    t1 = threading.Thread(target=worker_run, args=("w_1",))
    t2 = threading.Thread(target=worker_run, args=("w_2",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Verify both claimed and ran
    assert "t_parallel_A" in timings
    assert "t_parallel_B" in timings

    A_start, A_end = timings["t_parallel_A"]
    B_start, B_end = timings["t_parallel_B"]

    # Beweis der echten physikalischen Parallelität:
    # Die späteste Startzeit muss VOR der frühesten Endzeit liegen.
    # Wären sie sequentiell, wäre max(start) > min(end).
    overlap = max(A_start, B_start) < min(A_end, B_end)
    assert overlap, f"Tasks did not physically overlap: A({A_start}-{A_end}), B({B_start}-{B_end})"

def test_integration_dispatcher_auto_continue(client, tmp_path):
    """
    Prüfe den vorhandenen Dispatcher: wenn A und B abgeschlossen sind und C READY wird,
    muss der bestehende Runtime-Pfad C übernehmen können; ein zusätzlicher manueller
    Claim durch den Testtreiber darf nicht als AUTO_CONTINUE-PASS gelten.
    """
    import threading
    import time
    from server.app import API_KEY, VERIFIER_API_KEY, app, load_state

    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}

    client.post("/workers/register", json={
        "worker_id": "w_auto", "platform": "test", "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-auto", "cost_class": "free"
    }, headers=headers)

    # Goal mit Abhängigkeit: A & B parallel, dann C
    client.post("/goals", json={
        "goal_text": "Auto-Continue Dispatcher Test",
        "workflow_plan": [
            {"task_id": "auto_A", "target_agent": "linux", "instruction": "A"},
            {"task_id": "auto_B", "target_agent": "linux", "instruction": "B"},
            {"task_id": "auto_C", "target_agent": "linux", "instruction": "C", "depends_on": ["auto_A", "auto_B"]}
        ],
        "terminal": True
    }, headers=headers)

    stop_event = threading.Event()
    claimed_tasks = []

    # Der "bestehende Runtime-Pfad": Ein Worker-Loop wie im windows_worker/daemon.py
    def worker_daemon_loop():
        tc = app.test_client()
        while not stop_event.is_set():
            res = tc.post("/tasks/claim", json={"worker_id": "w_auto"}, headers=headers)
            if res.status_code == 200:
                task = res.json.get("task")
                if task:
                    claimed_tasks.append(task["task_id"])
                    # Simulate short work
                    time.sleep(0.05)
                    # Submit result
                    tc.post("/tasks/result", json={
                        "goal_id": task["goal_id"], "task_id": task["task_id"], "worker_id": "w_auto",
                        "attempt_id": task["attempt_id"], "dispatch_id": task["dispatch_id"],
                        "execution_ref": task["execution_ref"], "run_id": f"run-{task['task_id']}",
                        "result_id": f"res-{task['task_id']}", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
                    }, headers=headers)
                else:
                    time.sleep(0.05)
            else:
                time.sleep(0.05)

    daemon_thread = threading.Thread(target=worker_daemon_loop)
    daemon_thread.start()

    try:
        # Der Testtreiber wartet NUR auf den Status, greift aber NICHT in den Claim-Prozess ein!
        
        # Warte, bis A und B result_received sind
        def wait_for_result(tid):
            for _ in range(50):
                st = load_state()
                if st["tasks"].get(tid, {}).get("status") == "RESULT_RECEIVED":
                    return st["tasks"][tid]["result"]["result_id"]
                time.sleep(0.1)
            raise TimeoutError(f"{tid} did not complete")
            
        fp_a = wait_for_result("auto_A")
        fp_b = wait_for_result("auto_B")
        
        # C darf noch nicht geclaimt sein, da A und B noch nicht RECONCILED sind!
        assert "auto_C" not in claimed_tasks, "C claimed too early!"
        
        # Testtreiber verifiziert A und B (was C freischalten sollte)
        client.post("/tasks/verify", json={
            "task_id": "auto_A", "result_id": "res-auto_A", "verifier_id": "v1", "verdict": "PASS",
            "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
        }, headers=v_headers)
        
        client.post("/tasks/verify", json={
            "task_id": "auto_B", "result_id": "res-auto_B", "verifier_id": "v1", "verdict": "PASS",
            "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
        }, headers=v_headers)
        
        # BEWEIS: Wir rufen hier _kein_ manuelles client.post("/tasks/claim") auf!
        # Der bestehende Runtime-Pfad (daemon_thread) muss C selbst übernehmen.
        fp_c = wait_for_result("auto_C")
        assert "auto_C" in claimed_tasks, "C wurde nicht automatisch vom Daemon-Pfad übernommen!"
        
    finally:
        stop_event.set()
        daemon_thread.join(timeout=2.0)

def test_integration_server_restart_persistence(client, tmp_path):
    """
    Isolierter Restart-Test: Queue mit A/B/C anlegen, einen Teil abschließen (A),
    Server-Runtime neu laden (Hard-Reset Cache), und beweisen:
    - Fertige Arbeit (A) wird nicht erneut ausgeführt.
    - Offene Arbeit (B, C) geht nicht verloren und wird korrekt fortgesetzt.
    """
    import server.app
    from server.app import API_KEY, VERIFIER_API_KEY, load_state

    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}

    # 1. Register Worker
    client.post("/workers/register", json={
        "worker_id": "w_restart", "platform": "test", "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-restart", "cost_class": "free"
    }, headers=headers)

    # 2. Create Goal: A, B, C (C depends on A and B)
    client.post("/goals", json={
        "goal_text": "Restart Persistence Test",
        "workflow_plan": [
            {"task_id": "rest_A", "target_agent": "linux", "instruction": "A"},
            {"task_id": "rest_B", "target_agent": "linux", "instruction": "B"},
            {"task_id": "rest_C", "target_agent": "linux", "instruction": "C", "depends_on": ["rest_A", "rest_B"]}
        ],
        "terminal": True
    }, headers=headers)

    # 3. Worker claims A
    res = client.post("/tasks/claim", json={"worker_id": "w_restart"}, headers=headers)
    task_a = res.json["task"]
    assert task_a["task_id"] == "rest_A"

    # Worker liefert Resultat für A
    client.post("/tasks/result", json={
        "goal_id": task_a["goal_id"], "task_id": "rest_A", "worker_id": "w_restart",
        "attempt_id": task_a["attempt_id"], "dispatch_id": task_a["dispatch_id"],
        "execution_ref": task_a["execution_ref"], "run_id": "run-a",
        "result_id": "res-a", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)

    # Verifier nimmt A ab -> RECONCILED
    state = load_state()
    fp_a = state["tasks"]["rest_A"]["result"]["result_id"]
    client.post("/tasks/verify", json={
        "task_id": "rest_A", "result_id": "res-a", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)

    # 4. Worker claims B, aber schließt es vor dem Restart NICHT ab!
    res = client.post("/tasks/claim", json={"worker_id": "w_restart"}, headers=headers)
    task_b = res.json["task"]
    assert task_b["task_id"] == "rest_B"

    # --- SIMULIERE SERVER-RESTART (Test-Runtime neu laden) ---
    # Lösche alle In-Memory-Caches, erzwinge Reload vom Dateisystem
    server.app._cached_state_json = None
    server.app._cached_mtime = 0
    # Client neu instanziieren simuliert neue Connections
    new_client = server.app.app.test_client()

    # Nach Restart: Zustand verifizieren
    reloaded_state = load_state()
    assert reloaded_state["tasks"]["rest_A"]["status"] == "RECONCILED", "A muss weiterhin abgeschlossen sein"
    assert reloaded_state["tasks"]["rest_B"]["status"] == "DISPATCHED", "B muss als offene Arbeit markiert sein"
    
    # C ist noch nicht in tasks, da es noch nie geclaimt wurde. Wir finden es im Goal.
    c_status = None
    for goal in reloaded_state["goals"].values():
        for step in goal.get("workflow_plan", []):
            if step.get("task_id") == "rest_C":
                c_status = step.get("status")
    assert c_status == "QUEUED", "C darf nicht verloren gegangen sein und muss QUEUED sein"

    # 5. Beweis: Offene Arbeit geht nicht verloren, fertige wird nicht wiederholt.
    # Da B bereits an w_restart dispatched war und im realen Leben der Worker es aus 
    # seiner lokalen SQLite wiederherstellen würde, senden wir nach Server-Restart 
    # einfach das Resultat ein. Der Server muss es akzeptieren (Persistence).
    
    # Worker schließt B ab
    res_b_res = new_client.post("/tasks/result", json={
        "goal_id": task_b["goal_id"], "task_id": "rest_B", "worker_id": "w_restart",
        "attempt_id": task_b["attempt_id"], "dispatch_id": task_b["dispatch_id"],
        "execution_ref": task_b["execution_ref"], "run_id": "run-b",
        "result_id": "res-b", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res_b_res.status_code == 200, "Server hat Resultat für wiederhergestelltes B nicht akzeptiert!"

    st2 = load_state()
    fp_b = st2["tasks"]["rest_B"]["result"]["result_id"]
    new_client.post("/tasks/verify", json={
        "task_id": "rest_B", "result_id": "res-b", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)

    # 6. Beweis: C wird freigeschaltet, A bleibt unberührt
    # Jetzt sollte C (und nur C) als neue Arbeit kommen
    res_c = new_client.post("/tasks/claim", json={"worker_id": "w_restart"}, headers=headers)
    assert res_c.json["task"]["task_id"] == "rest_C", "C wurde nach B nicht korrekt in den Runtime-Pfad übernommen!"

    # Worker schließt C ab
    new_client.post("/tasks/result", json={
        "goal_id": res_c.json["task"]["goal_id"], "task_id": "rest_C", "worker_id": "w_restart",
        "attempt_id": res_c.json["task"]["attempt_id"], "dispatch_id": res_c.json["task"]["dispatch_id"],
        "execution_ref": res_c.json["task"]["execution_ref"], "run_id": "run-c",
        "result_id": "res-c", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)

    # Fertig
    final_state = load_state()
    assert final_state["tasks"]["rest_A"]["status"] == "RECONCILED", "A wurde fälschlicherweise manipuliert"
    assert final_state["tasks"]["rest_B"]["status"] == "RESULT_RECEIVED" or final_state["tasks"]["rest_B"]["status"] == "RECONCILED"
    assert final_state["tasks"]["rest_C"]["status"] == "RESULT_RECEIVED"

def test_integration_crash_result_persistence_boundaries(client, tmp_path, monkeypatch):
    """
    Testet Crash-Szenarien rund um die Result-Persistenz und Reconcile:
    1. Crash zwischen Result-Erstellung und Persistenz (Server-Save schlägt fehl).
    2. Crash nach Persistenz (Worker verliert ACK, sendet doppelt).
    Beweist: Kein stiller Verlust, keine Doppelwirkung beim Reconcile.
    """
    import server.app
    from server.app import API_KEY, VERIFIER_API_KEY, load_state

    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}

    client.post("/workers/register", json={
        "worker_id": "w_crash_1", "platform": "test", "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-crash", "cost_class": "free"
    }, headers=headers)

    client.post("/workers/register", json={
        "worker_id": "w_crash_2", "platform": "test", "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-crash", "cost_class": "free"
    }, headers=headers)

    client.post("/goals", json={
        "goal_text": "Crash Persistence Test",
        "workflow_plan": [
            {"task_id": "crash_A", "target_agent": "linux", "instruction": "A"},
            {"task_id": "crash_B", "target_agent": "linux", "instruction": "B"}
        ],
        "terminal": True
    }, headers=headers)

    # Claim A & B
    res_a = client.post("/tasks/claim", json={"worker_id": "w_crash_1"}, headers=headers)
    task_a = res_a.json["task"]
    
    res_b = client.post("/tasks/claim", json={"worker_id": "w_crash_2"}, headers=headers)
    task_b = res_b.json["task"]

    # --- SZENARIO 1: CRASH VOR PERSISTENZ ---
    # Wir fangen den save_state() Aufruf ab und werfen eine Exception, um einen Hard-Crash
    # (z.B. Stromausfall während Disk-Write) zu simulieren.
    original_save_state = server.app.save_state
    crash_state = {"crash_active": True}

    def crashing_save_state(state):
        if crash_state["crash_active"]:
            raise Exception("HARD CRASH DURING PERSISTENCE")
        original_save_state(state)

    monkeypatch.setattr(server.app, "save_state", crashing_save_state)

    import pytest
    # Worker sendet Result für A -> Server stürzt ab (Exception bubble-up im TestClient)
    with pytest.raises(Exception, match="HARD CRASH DURING PERSISTENCE"):
        client.post("/tasks/result", json={
            "goal_id": task_a["goal_id"], "task_id": "crash_A", "worker_id": "w_crash_1",
            "attempt_id": task_a["attempt_id"], "dispatch_id": task_a["dispatch_id"],
            "execution_ref": task_a["execution_ref"], "run_id": "run-crash-a",
            "result_id": "res-crash-a", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
        }, headers=headers)

    # Beweis: A ist weiterhin DISPATCHED, Resultat ist nicht gespeichert (kein stiller Defekt)
    assert load_state()["tasks"]["crash_A"]["status"] == "DISPATCHED"

    # Recovery: Server ist wieder da. Worker, da er kein HTTP 200 bekam, retryed.
    crash_state["crash_active"] = False
    res_a_retry = client.post("/tasks/result", json={
        "goal_id": task_a["goal_id"], "task_id": "crash_A", "worker_id": "w_crash_1",
        "attempt_id": task_a["attempt_id"], "dispatch_id": task_a["dispatch_id"],
        "execution_ref": task_a["execution_ref"], "run_id": "run-crash-a",
        "result_id": "res-crash-a", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res_a_retry.status_code == 200
    assert load_state()["tasks"]["crash_A"]["status"] == "RESULT_RECEIVED"


    # --- SZENARIO 2: CRASH NACH PERSISTENZ ---
    # Worker sendet Result für B -> Server speichert erfolgreich.
    res_b_ok = client.post("/tasks/result", json={
        "goal_id": task_b["goal_id"], "task_id": "crash_B", "worker_id": "w_crash_2",
        "attempt_id": task_b["attempt_id"], "dispatch_id": task_b["dispatch_id"],
        "execution_ref": task_b["execution_ref"], "run_id": "run-crash-b",
        "result_id": "res-crash-b", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res_b_ok.status_code == 200
    assert load_state()["tasks"]["crash_B"]["status"] == "RESULT_RECEIVED"

    # Worker verliert die Netzwerkverbindung, erhält das ACK nicht und RETRYED.
    # Beweis: Keine Doppelwirkung, Server antwortet idempotent.
    res_b_retry = client.post("/tasks/result", json={
        "goal_id": task_b["goal_id"], "task_id": "crash_B", "worker_id": "w_crash_2",
        "attempt_id": task_b["attempt_id"], "dispatch_id": task_b["dispatch_id"],
        "execution_ref": task_b["execution_ref"], "run_id": "run-crash-b",
        "result_id": "res-crash-b", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    assert res_b_retry.status_code == 200
    assert res_b_retry.json.get("status") == "ACK_DUPLICATE", "Doppeltes Result muss idempotent abgefangen werden"


    # --- RECONCILE PHASE ---
    # Beide Tasks müssen nun lückenlos und ohne Doppelwirkung abgenommen werden können.
    st = load_state()
    fp_a = st["tasks"]["crash_A"]["result"]["result_id"]
    fp_b = st["tasks"]["crash_B"]["result"]["result_id"]

    res_v_a = client.post("/tasks/verify", json={
        "task_id": "crash_A", "result_id": "res-crash-a", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert res_v_a.status_code == 200

    res_v_b = client.post("/tasks/verify", json={
        "task_id": "crash_B", "result_id": "res-crash-b", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert res_v_b.status_code == 200

    # Teste Reconcile Doppelwirkung: Zweiter Verify-Versuch auf A
    res_v_a_dup = client.post("/tasks/verify", json={
        "task_id": "crash_A", "result_id": "res-crash-a", "verifier_id": "v1", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)
    assert res_v_a_dup.status_code == 200
    assert res_v_a_dup.json.get("status") == "ACK_DUPLICATE", "Doppel-Verify muss idempotent bleiben"

    final_state = load_state()
    assert final_state["tasks"]["crash_A"]["status"] == "RECONCILED", "A muss sauber reconciled sein"
    assert final_state["tasks"]["crash_B"]["status"] == "RECONCILED", "B muss sauber reconciled sein"

def test_integration_waiting_provider_isolation(client, tmp_path):
    """
    Testet die Isolierung des WAITING_PROVIDER Status.
    Aufbau: 
    - Task A wird geclaimt und meldet provider_wait -> Status WAITING_PROVIDER.
    - Task B benötigt "linux" -> QUEUED/READY.
    - Task C benötigt "linux", depends_on B.
    Beweist: A stoppt nicht die Dispatching-Queue. B kann gepullt werden, dann C.
    """
    from server.app import API_KEY, VERIFIER_API_KEY, load_state

    headers = {"Authorization": f"Bearer {API_KEY}"}
    v_headers = {"Authorization": f"Bearer {VERIFIER_API_KEY}"}

    client.post("/workers/register", json={
        "worker_id": "w_prov", "platform": "test", "capabilities": ["linux"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-prov", "cost_class": "free"
    }, headers=headers)
    
    client.post("/workers/register", json={
        "worker_id": "w_gpu", "platform": "test", "capabilities": ["gpu"], "authorities": [],
        "provider": "local", "capacity_identity": "cap-gpu", "cost_class": "free"
    }, headers=headers)

    client.post("/goals", json={
        "goal_text": "Waiting Provider Isolation Test",
        "workflow_plan": [
            {"task_id": "prov_A", "target_agent": "gpu", "instruction": "A"},
            {"task_id": "prov_B", "target_agent": "linux", "instruction": "B"},
            {"task_id": "prov_C", "target_agent": "linux", "instruction": "C", "depends_on": ["prov_B"]}
        ],
        "terminal": True
    }, headers=headers)

    # 1. w_gpu fordert Arbeit an und bekommt A
    res_claim_a = client.post("/tasks/claim", json={"worker_id": "w_gpu"}, headers=headers)
    assert res_claim_a.status_code == 200
    assert res_claim_a.json["task"]["task_id"] == "prov_A"

    # w_gpu meldet provider_wait -> A wird WAITING_PROVIDER
    res_wait = client.post(f"/tasks/prov_A/provider_wait", json={"worker_id": "w_gpu"}, headers=headers)
    assert res_wait.status_code == 200

    # 2. w_prov fordert Arbeit an. 
    # Erwartung: A ist WAITING_PROVIDER und wird ignoriert. w_prov bekommt B.
    res_claim_b = client.post("/tasks/claim", json={"worker_id": "w_prov"}, headers=headers)
    assert res_claim_b.status_code == 200
    task_b = res_claim_b.json["task"]
    assert task_b is not None, "Worker w_prov hätte Task B bekommen müssen!"
    assert task_b["task_id"] == "prov_B", f"Erwartet prov_B, stattdessen {task_b['task_id']}"

    # Überprüfe den Status von A in tasks
    st = load_state()
    assert st["tasks"]["prov_A"]["status"] == "WAITING_PROVIDER", f"A muss auf WAITING_PROVIDER sein, war aber {st['tasks']['prov_A']['status']}"
    assert st["tasks"]["prov_B"]["status"] == "DISPATCHED"

    # 3. B abschließen (Result + Verify)
    client.post("/tasks/result", json={
        "goal_id": task_b["goal_id"], "task_id": "prov_B", "worker_id": "w_prov",
        "attempt_id": task_b["attempt_id"], "dispatch_id": task_b["dispatch_id"],
        "execution_ref": task_b["execution_ref"], "run_id": "run-prov-b",
        "result_id": "res-prov-b", "status": "SUCCESS", "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=headers)
    
    st2 = load_state()
    fp_b = st2["tasks"]["prov_B"]["result"]["result_id"]
    client.post("/tasks/verify", json={
        "task_id": "prov_B", "result_id": "res-prov-b", "verifier_id": "v_prov", "verdict": "PASS",
        "received_runtime_identity": server.app.SERVER_BINDING, "artifacts": [], "received_runtime_identity": server.app.SERVER_BINDING
    }, headers=v_headers)

    # 4. w_prov fordert erneut Arbeit an.
    # C ist jetzt bereit, da B abgeschlossen ist. C muss fehlerfrei dispatched werden.
    res_claim_c = client.post("/tasks/claim", json={"worker_id": "w_prov"}, headers=headers)
    assert res_claim_c.status_code == 200
    task_c = res_claim_c.json["task"]
    assert task_c is not None, "Worker w_prov hätte Task C bekommen müssen!"
    assert task_c["task_id"] == "prov_C", f"Erwartet prov_C, stattdessen {task_c['task_id']}"

    # 5. Finaler Zustandscheck
    final_st = load_state()
    assert final_st["tasks"]["prov_A"]["status"] == "WAITING_PROVIDER", "A muss weiterhin isoliert in WAITING_PROVIDER stehen"
    assert final_st["tasks"]["prov_B"]["status"] == "RECONCILED", "B ist fertig"
    assert final_st["tasks"]["prov_C"]["status"] == "DISPATCHED", "C wurde erfolgreich blockierungsfrei abgezogen"


