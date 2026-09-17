import sys
import pytest
import subprocess
import json
from pathlib import Path
import os
import importlib.util

ROOT = Path(__file__).parent.parent.resolve()
CONTINUE_SCRIPT = ROOT / "scripts" / "courier_continue.py"
CONTINUE_SPEC = importlib.util.spec_from_file_location(
    "courier_continue_under_test", CONTINUE_SCRIPT
)
assert CONTINUE_SPEC and CONTINUE_SPEC.loader
continue_module = importlib.util.module_from_spec(CONTINUE_SPEC)
CONTINUE_SPEC.loader.exec_module(continue_module)

def setup_ledger(tmp_path, unproven_edges, blocker, proven_edges=None, active_writers=None, collision_scope=None, blocker_owner="Human"):
    record = {
        "PROJECT": "Courier",
        "GOAL": "TEST-GOAL",
        "CURRENT_SHA": "0000000000000000000000000000000000000000",
        "BRANCH": "test-branch",
        "RUNTIME_IDENTITY": "0000000000000000000000000000000000000000",
        "RUNTIME_OWNER": "test",
        "STATUS": "TEST",
        "PROVEN_EDGES": proven_edges or [],
        "UNPROVEN_EDGES": unproven_edges,
        "FIRST_CAUSAL_BLOCKER": blocker,
        "BLOCKER_OWNER": blocker_owner,
        "NEXT_EXECUTABLE_ACTION": "test",
        "ACTIVE_WRITERS": active_writers or [],
        "COLLISION_SCOPE": collision_scope or [],
        "GOALS_SUBMITTED": 0,
        "TASKS_COMPLETED": 0,
        "WORKERS_USED": 0,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "UNKNOWN",
        "QUEUE_INDEPENDENT": "NO",
        "LAST_EVIDENCE": [],
        "LAST_UPDATED_BY": "test",
        "CONTINUATION_CHECKPOINT": "none"
    }
    
    guard = {
        "acceptance_predicate": {
            "name": "Global-Stop",
            "version": "1.0",
            "required_results": ["ISSUE_STATE"],
            "results": {
                "ISSUE_STATE": {
                    "status": "UNKNOWN",
                    "observed_value": "NO_FURTHER_ACTION",
                    "evidence_urls": ["https://test.com"]
                }
            }
        },
        "binding": {
            "branch": "test-branch",
            "current_sha": "0000000000000000000000000000000000000000",
            "runtime_identity": "0000000000000000000000000000000000000000"
        },
        "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-17T12:00:00Z","evidence_sha":"0000000000000000000000000000000000000000","runtime_binding":"0000000000000000000000000000000000000000","validity":"UNKNOWN","reason":"test"}],
        "flow": [
            "EXECUTION",
            "EVIDENCE",
            "ACCEPTANCE_GUARD",
            "LEDGER_TRANSITION",
            "NEXT_EXECUTABLE_ACTION"
        ],
        "transition_state": "PROVISIONAL",
        "worker_state": "IDLE/YIELDED"
    }
    
    record_path = tmp_path / "record.json"
    guard_path = tmp_path / "guard.json"
    ledger_path = tmp_path / "agent_handoff_ledger.json"
    
    record_path.write_text(json.dumps(record))
    guard_path.write_text(json.dumps(guard))
    
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "agent_handoff_ledger.py"
    
    subprocess.run([sys.executable, str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)
    return ledger_path

def run_continue(ledger_path, mock_sha="0000000000000000000000000000000000000000", mock_branch="test-branch", run=False):
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "courier_continue.py"
    
    env = os.environ.copy()
    env.update({"MOCK_SHA": mock_sha, "MOCK_BRANCH": mock_branch, "MOCK_LEDGER": str(ledger_path), "PYTHONPATH": str(repo_dir)})
    
    cmd = [sys.executable, str(script)]
    cmd.append("--once")
    if run:
        cmd.append("--run")
        
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result


def test_frontier_uses_only_durable_unproven_edges():
    rec = {
        "PROVEN_EDGES": [],
        "UNPROVEN_EDGES": ["PUBLICATION VERIFICATION"],
    }
    tasks = continue_module.compute_frontier(rec)
    assert [task["edge_name"] for task in tasks] == ["PUBLICATION VERIFICATION"]


def test_empty_unproven_frontier_does_not_manufacture_plan_tasks():
    tasks = continue_module.compute_frontier(
        {"PROVEN_EDGES": [], "UNPROVEN_EDGES": []}
    )
    assert tasks == []


def test_empty_frontier_does_not_print_false_clean_idle(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "NONE")
    result = run_continue(ledger_path, run=True)
    assert result.returncode == 0, result.stderr
    assert "GLOBAL STOP: CLEAN_IDLE" not in result.stdout
    assert "Empty frontier is not accepted completion" in result.stdout
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert data["record"]["CLEAN_IDLE"] == "NO"
    assert data["record"]["QUEUE_INDEPENDENT"] == "NO"
    assert data["acceptance_guard"]["transition_state"] == "PROVISIONAL"


@pytest.mark.parametrize(
    "edge",
    [
        "POST-PILOT HARDENING",
        "RELEASE - SAFE_AUTOMATABLE_PREPARATION",
        "RELEASE - AUTHORIZED_MACHINE_ACTION",
        "PUBLICATION VERIFICATION",
    ],
)
def test_placeholder_or_external_steps_cannot_self_report_success(edge, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = {"edge_name": edge, "instruction": f"Prove edge: {edge}"}
    _, success, blocker = continue_module.execute_task(task, tmp_path / "ledger.json", {})
    assert success is False
    assert blocker


def test_failed_task_is_not_resubmitted_in_same_run(tmp_path):
    ledger_path = setup_ledger(
        tmp_path, ["PUBLICATION VERIFICATION"], "NONE"
    )
    result = run_continue(ledger_path, run=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("SUBMITTING TASK: PUBLICATION VERIFICATION") == 1
    state = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert "PUBLICATION VERIFICATION" in state["record"]["UNPROVEN_EDGES"]
    assert "PUBLICATION VERIFICATION" not in state["record"]["PROVEN_EDGES"]


def test_execution_success_cannot_promote_its_own_edge(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    edge = "SALES PACKAGE"
    ledger_path = setup_ledger(tmp_path, [edge], "NONE")
    bundle = continue_module.load_bundle(ledger_path)
    task = {"edge_name": edge, "instruction": f"Prove edge: {edge}"}
    _, success, blocker = continue_module.execute_task(
        task, ledger_path, bundle["record"]
    )
    assert success is True
    assert blocker is None

    updated = continue_module.update_ledger(
        ledger_path, edge, blocker, bundle
    )
    assert edge not in updated["record"]["PROVEN_EDGES"]
    assert edge in updated["record"]["UNPROVEN_EDGES"]
    assert updated["record"]["QUEUE_INDEPENDENT"] == "NO"
    assert updated["record"]["CLEAN_IDLE"] == "NO"
    assert updated["record"]["STATUS"] == "WAITING_ACCEPTANCE_GUARD"

def test_multiple_independent_tasks_concurrent_progress(tmp_path):
    ledger_path = setup_ledger(
        tmp_path,
        [
            "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION",
            "SALES PACKAGE",
            "POST-PILOT HARDENING",
        ],
        "HUMAN_REQUIRED",
        proven_edges=[],
    )
    res = run_continue(ledger_path, run=True)
    
    assert "Executing/Delegating task: Prove edge: PILOT INTAKE" in res.stdout
    assert "Executing/Delegating task: Prove edge: SALES PACKAGE" in res.stdout
    assert "Executing/Delegating task: Prove edge: POST-PILOT HARDENING" in res.stdout

def test_busy_worker_independent_task_continues(tmp_path):
    ledger_path = setup_ledger(
        tmp_path,
        ["LEDGER/HANDOFF", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION"],
        "NONE",
        collision_scope=["LEDGER/HANDOFF"],
    )
    res = run_continue(ledger_path, run=True)
    
    assert "Prove edge: PUBLIC DEPLOYMENT" in res.stdout

def test_human_gate_independent_task_continues(tmp_path):
    ledger_path = setup_ledger(
        tmp_path,
        [
            "RELEASE - IRREVERSIBLE_HUMAN_ACTION",
            "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION",
        ],
        "HUMAN_REQUIRED",
        proven_edges=["LEDGER/HANDOFF"],
    )
    res = run_continue(ledger_path, run=True)
    
    assert "Prove edge: PUBLIC DEPLOYMENT" in res.stdout

def test_money_gate_free_task_continues(tmp_path):
    ledger_path = setup_ledger(
        tmp_path,
        ["PR41 ACCEPTANCE", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - IRREVERSIBLE_HUMAN_ACTION"],
        "MONEY_REQUIRED",
        proven_edges=["LEDGER/HANDOFF"],
    )
    res = run_continue(ledger_path, run=True)
    
    assert "Prove edge: PR41 ACCEPTANCE" in res.stdout

def test_provider_unavailable_alternate_worker_continues(tmp_path):
    ledger_path = setup_ledger(
        tmp_path,
        ["LEDGER/HANDOFF"],
        "PROVIDER_QUOTA_EXHAUSTED",
        blocker_owner="other_worker",
    )
    res = run_continue(ledger_path, run=True)
    
    assert "Prove edge: LEDGER/HANDOFF" in res.stdout

def test_writer_collision_serialize_colliding_scope(tmp_path):
    ledger_path = setup_ledger(
        tmp_path,
        ["LEDGER/HANDOFF", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION"],
        "NONE",
        collision_scope=["LEDGER/HANDOFF"],
    )
    res = run_continue(ledger_path, run=True)
    
    assert "Prove edge: PUBLIC DEPLOYMENT" in res.stdout

def test_stale_ledger_fail_closed(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "NONE")
    res = run_continue(ledger_path, mock_sha="1111111111111111111111111111111111111111")
    assert res.returncode == 0
    assert "Ledger is stale. Fail closed" in res.stdout

def test_all_scopes_blocked_true_global_stop(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "HUMAN_REQUIRED_PUBLIC_REPO_VISIBILITY", proven_edges=["LEDGER/HANDOFF", "PR41 ACCEPTANCE", "RELEASE - SAFE_AUTOMATABLE_PREPARATION", "RELEASE - AUTHORIZED_MACHINE_ACTION", "RELEASE - IRREVERSIBLE_HUMAN_ACTION", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION", "PUBLIC DEPLOYMENT - AUTHORIZED_MACHINE_ACTION", "PUBLIC DEPLOYMENT - IRREVERSIBLE_HUMAN_ACTION", "PUBLICATION VERIFICATION", "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION", "PILOT INTAKE - AUTHORIZED_MACHINE_ACTION", "PILOT INTAKE - IRREVERSIBLE_HUMAN_ACTION", "SALES PACKAGE", "FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION", "FIRST PILOT - AUTHORIZED_MACHINE_ACTION", "FIRST PILOT - IRREVERSIBLE_HUMAN_ACTION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - AUTHORIZED_MACHINE_ACTION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - IRREVERSIBLE_HUMAN_ACTION", "POST-PILOT HARDENING", "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION", "EXTERNAL_PUBLICATION - AUTHORIZED_MACHINE_ACTION", "EXTERNAL_PUBLICATION - IRREVERSIBLE_HUMAN_ACTION", "ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION", "ONBOARD_FIRST_PILOT_CUSTOMER - AUTHORIZED_MACHINE_ACTION", "ONBOARD_FIRST_PILOT_CUSTOMER - IRREVERSIBLE_HUMAN_ACTION"])
    res = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "scripts" / "courier_continue.py"), "--run", "--once"], env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000"), capture_output=True, text=True)
    assert res.returncode == 0
    assert "GLOBAL STOP: CLEAN_IDLE" not in res.stdout
    assert "Empty frontier is not accepted completion" in res.stdout

def test_capability_insufficient_cannot_claim(tmp_path):
    # LEDGER/HANDOFF requires "git", "file_write"
    ledger_path = setup_ledger(
        tmp_path, ["LEDGER/HANDOFF", "PUBLICATION VERIFICATION"], "NONE"
    )
    
    # Run with limited capabilities (only shell and http_client, missing git/file_write)
    env = os.environ.copy()
    env.update({"MOCK_SHA": "0000000000000000000000000000000000000000", "MOCK_BRANCH": "test-branch", "MOCK_LEDGER": str(ledger_path), "COURIER_WORKER_CAPABILITIES": "shell,http_client"})
    
    repo_dir = Path(__file__).parent.parent.resolve()
    runner = repo_dir / "scripts" / "courier_continue.py"
    res = subprocess.run([sys.executable, str(runner), "--once"], env=env, capture_output=True, text=True)
    
    assert res.returncode == 0
    # Because LEDGER/HANDOFF cannot be claimed, it should fall back to an independent task it CAN claim.
    # PUBLICATION VERIFICATION needs "http_client" so it should claim that.
    assert "Prove edge: PUBLICATION VERIFICATION" in res.stdout
    assert "Prove edge: LEDGER/HANDOFF" not in res.stdout

def test_worker_loss_takeover_and_handoff(tmp_path):
    # Simulates worker loss and takeover by a different machine (Mac -> Windows)
    # Both use the same Motor primitive contract via `courier_continue.py`
    ledger_path = setup_ledger(
        tmp_path,
        ["PUBLICATION VERIFICATION", "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION"],
        "NONE",
    )
    
    # Worker 1 (Mac) starts but is interrupted, so it has no collision scope but we simulate a new process
    env1 = os.environ.copy()
    env1.update({"MOCK_SHA": "0000000000000000000000000000000000000000", "MOCK_BRANCH": "test-branch", "MOCK_LEDGER": str(ledger_path), "COURIER_WORKER_CAPABILITIES": "http_client"})
    
    repo_dir = Path(__file__).parent.parent.resolve()
    runner = repo_dir / "scripts" / "courier_continue.py"
    
    res1 = subprocess.run([sys.executable, str(runner)], env=env1, capture_output=True, text=True)
    assert "Prove edge: PUBLICATION VERIFICATION" in res1.stdout
    
    # Worker 2 (Windows) picks up another independent edge because it has different capabilities
    env2 = os.environ.copy()
    env2.update({"MOCK_SHA": "0000000000000000000000000000000000000000", "MOCK_BRANCH": "test-branch", "MOCK_LEDGER": str(ledger_path), "COURIER_WORKER_CAPABILITIES": "email_processing"})
    
    res2 = subprocess.run([sys.executable, str(runner)], env=env2, capture_output=True, text=True)
    assert "Prove edge: PILOT INTAKE" in res2.stdout


def test_capability_based_routing_claims_eligible(tmp_path):
    ledger_path = setup_ledger(tmp_path, ["PUBLICATION VERIFICATION"], "NONE")
    
    # Only has HTTP client capability
    env = os.environ.copy()
    env.update({"MOCK_SHA": "0000000000000000000000000000000000000000", "MOCK_BRANCH": "test-branch", "MOCK_LEDGER": str(ledger_path), "COURIER_WORKER_CAPABILITIES": "http_client"})
    
    repo_dir = Path(__file__).parent.parent.resolve()
    runner = repo_dir / "scripts" / "courier_continue.py"
    res = subprocess.run([sys.executable, str(runner), "--once"], env=env, capture_output=True, text=True)
    
    # It should pick PUBLICATION VERIFICATION since it's independent and matches capabilities
    assert "Prove edge: PUBLICATION VERIFICATION" in res.stdout


def test_missing_physical_proof_prevents_acceptance(tmp_path):
    ledger_path = setup_ledger(tmp_path, [], "NONE", proven_edges=["LEDGER/HANDOFF", "PR41 ACCEPTANCE", "RELEASE - SAFE_AUTOMATABLE_PREPARATION", "RELEASE - AUTHORIZED_MACHINE_ACTION", "RELEASE - IRREVERSIBLE_HUMAN_ACTION", "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION", "PUBLIC DEPLOYMENT - AUTHORIZED_MACHINE_ACTION", "PUBLIC DEPLOYMENT - IRREVERSIBLE_HUMAN_ACTION", "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION", "PILOT INTAKE - AUTHORIZED_MACHINE_ACTION", "PILOT INTAKE - IRREVERSIBLE_HUMAN_ACTION", "SALES PACKAGE", "FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION", "FIRST PILOT - AUTHORIZED_MACHINE_ACTION", "FIRST PILOT - IRREVERSIBLE_HUMAN_ACTION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - AUTHORIZED_MACHINE_ACTION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED - IRREVERSIBLE_HUMAN_ACTION", "POST-PILOT HARDENING", "EXTERNAL_PUBLICATION - SAFE_AUTOMATABLE_PREPARATION", "EXTERNAL_PUBLICATION - AUTHORIZED_MACHINE_ACTION", "EXTERNAL_PUBLICATION - IRREVERSIBLE_HUMAN_ACTION", "ONBOARD_FIRST_PILOT_CUSTOMER - SAFE_AUTOMATABLE_PREPARATION", "ONBOARD_FIRST_PILOT_CUSTOMER - AUTHORIZED_MACHINE_ACTION", "ONBOARD_FIRST_PILOT_CUSTOMER - IRREVERSIBLE_HUMAN_ACTION"])
    
    # Run continue
    res = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "scripts" / "courier_continue.py"), "--run", "--once"], env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000"), capture_output=True, text=True)
    
    with open(ledger_path, "r") as f:
        data = json.load(f)
        
    assert data["record"]["CLEAN_IDLE"] == "NO"
    assert data["record"]["QUEUE_INDEPENDENT"] == "NO"
    assert data["record"]["FIRST_CAUSAL_BLOCKER"] == "MISSING_PHYSICAL_ACCEPTANCE_EVIDENCE"
    assert data["history"][-1]["acceptance_guard"]["transition_state"] == "PROVISIONAL"

def test_valid_physical_proof_allows_acceptance(tmp_path):
    # Manually create the guard and record with valid evidence
    record = {
        "PROJECT": "Courier",
        "GOAL": "TEST-GOAL",
        "CURRENT_SHA": "0000000000000000000000000000000000000000",
        "BRANCH": "test-branch",
        "RUNTIME_IDENTITY": "0000000000000000000000000000000000000000",
        "RUNTIME_OWNER": "test",
        "STATUS": "TEST",
        "PROVEN_EDGES": ["LEDGER/HANDOFF", "PR41 ACCEPTANCE", "RELEASE", "PILOT INTAKE", "SALES PACKAGE", "FIRST PILOT", "POST-PILOT HARDENING", "PUBLIC DEPLOYMENT", "PUBLICATION VERIFICATION", "PAYMENT ONLY WHEN ACTUALLY REQUIRED", "EXTERNAL_PUBLICATION", "ONBOARD_FIRST_PILOT_CUSTOMER"],
        "UNPROVEN_EDGES": [],
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "BLOCKER_OWNER": "Human",
        "NEXT_EXECUTABLE_ACTION": "test",
        "ACTIVE_WRITERS": [],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 0,
        "TASKS_COMPLETED": 0,
        "WORKERS_USED": 0,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "UNKNOWN",
        "QUEUE_INDEPENDENT": "NO",
        "LAST_EVIDENCE": [],
        "LAST_UPDATED_BY": "test",
        "CONTINUATION_CHECKPOINT": "none"
    }
    
    guard = {
        "acceptance_predicate": {
            "name": "Global-Stop",
            "version": "1.0",
            "required_results": ["ISSUE_STATE"],
            "results": {
                "ISSUE_STATE": {
                    "status": "UNKNOWN",
                    "observed_value": "NO_FURTHER_ACTION",
                    "evidence_urls": ["https://test.com"]
                }
            }
        },
        "binding": {
            "branch": "test-branch",
            "current_sha": "0000000000000000000000000000000000000000",
            "runtime_identity": "0000000000000000000000000000000000000000"
        },
        "evidence": [{"source_url":"https://test.com","source_type":"MACHINE_ARTIFACT","observed_at":"2026-09-17T12:00:00Z","evidence_sha":"0000000000000000000000000000000000000000","runtime_binding":"0000000000000000000000000000000000000000","validity":"VALID","reason":"test","producer_id":"physical-worker","verifier_id":"independent-verifier"}],
        "flow": [
            "EXECUTION",
            "EVIDENCE",
            "ACCEPTANCE_GUARD",
            "LEDGER_TRANSITION",
            "NEXT_EXECUTABLE_ACTION"
        ],
        "transition_state": "PROVISIONAL",
        "worker_state": "IDLE/YIELDED"
    }
    
    import json
    record_path = tmp_path / "record.json"
    guard_path = tmp_path / "guard.json"
    ledger_path = tmp_path / "agent_handoff_ledger.json"
    
    record_path.write_text(json.dumps(record))
    guard_path.write_text(json.dumps(guard))
    
    repo_dir = Path(__file__).parent.parent.resolve()
    script = repo_dir / "scripts" / "agent_handoff_ledger.py"
    
    subprocess.run([sys.executable, str(script), "init", str(ledger_path), "--record", str(record_path), "--guard", str(guard_path)], check=True)

    res = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "scripts" / "courier_continue.py"), "--run", "--once"], env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000"), capture_output=True, text=True)
    
    with open(ledger_path, "r") as f:
        data = json.load(f)
        
    assert res.returncode == 0, res.stderr
    assert data["record"]["CLEAN_IDLE"] in ("YES", "NO")
    assert data["record"]["QUEUE_INDEPENDENT"] == "YES"
    assert data["history"][-1]["acceptance_guard"]["transition_state"] == "CANONICAL_ACCEPTED"

def test_blocked_dependent_does_not_freeze_independent(tmp_path):
    ledger_path = setup_ledger(
        tmp_path,
        unproven_edges=["RELEASE - SAFE_AUTOMATABLE_PREPARATION", "PUBLICATION VERIFICATION"],
        blocker="UNVERIFIED_EXTERNAL_EFFECT_RELEASE",
        proven_edges=["LEDGER/HANDOFF"],
    )
    repo_dir = Path(__file__).parent.parent.resolve()
    res = subprocess.run(
        [sys.executable, str(repo_dir / "scripts" / "courier_continue.py")],
        env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000"),
        capture_output=True, text=True, cwd=str(repo_dir),
    )
    assert res.returncode == 0, res.stderr
    assert "Selected Next Action" in res.stdout
    assert "GLOBAL STOP" not in res.stdout
    with open(ledger_path) as f:
        data = json.load(f)
    assert data["record"]["USER_CONTINUE_MESSAGES"] == 0


def test_zero_chat_replenishment_two_cycles(tmp_path):
    repo_dir = Path(__file__).parent.parent.resolve()
    proven = ["LEDGER/HANDOFF"]
    for cycle_unproven in (["PR41 ACCEPTANCE", "RELEASE"], ["RELEASE"]):
        cycle_dir = tmp_path / f"cycle{len(proven)}"
        cycle_dir.mkdir(exist_ok=True)
        ledger_path = setup_ledger(
            cycle_dir,
            unproven_edges=cycle_unproven,
            blocker="NONE",
            proven_edges=list(proven),
        )
        res = subprocess.run(
            [sys.executable, str(repo_dir / "scripts" / "courier_continue.py")],
            env=dict(os.environ, MOCK_LEDGER=str(ledger_path), MOCK_BRANCH="test-branch", MOCK_SHA="0000000000000000000000000000000000000000"),
            capture_output=True, text=True, cwd=str(repo_dir),
        )
        assert res.returncode == 0, res.stderr
        assert "Selected Next Action" in res.stdout
        with open(ledger_path) as f:
            data = json.load(f)
        assert data["record"]["USER_CONTINUE_MESSAGES"] == 0
        proven.append(cycle_unproven[0])
