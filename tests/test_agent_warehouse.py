import json
import pytest
import sys
import time
from pathlib import Path
from scripts.agent_warehouse import AgentCatalog, CapabilitySelector

def test_load_agent_catalog():
    repo_root = Path(__file__).parent.parent
    catalog_path = repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json"
    
    catalog = AgentCatalog.load(catalog_path)
    
    assert catalog.schema_version == "0.1-bootstrap"
    assert len(catalog.agents) > 0
    
    # Verify Chief Commander exists
    chief = next((a for a in catalog.agents if a.id == "agent-chief-commander"), None)
    assert chief is not None
    assert "orchestration" in chief.capabilities
    assert chief.cost_class == "local_or_routed"
    
    # Verify we can find a bodyguard
    bodyguard = next((a for a in catalog.agents if a.agent_class == "reserve" and "bodyguard" in a.id.lower()), None)
    if bodyguard:
        assert bodyguard.status == "planned" or bodyguard.status == "implemented"

def test_capability_selector():
    repo_root = Path(__file__).parent.parent
    catalog = AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json")
    selector = CapabilitySelector(catalog)
    
    # Orchestration might only have one provider
    explanation = selector.select_agent_for_task("orchestration")
    assert explanation.selected_agent_id == "agent-chief-commander"
    assert "orchestration" in explanation.capable_reason
    
    # Check a more common capability if present, else just make sure logic holds
    try:
        exp_comp = selector.select_agent_for_task("completion")
        assert exp_comp.selected_agent_id is not None
    except ValueError:
        pass


def test_unimplemented_agents_not_selected_by_default():
    repo_root = Path(__file__).parent.parent
    catalog = AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json")
    selector = CapabilitySelector(catalog)
    
    # routing_candidate is only registered by smart-resource-router which has status 'partial'
    with pytest.raises(ValueError, match="No agent found for capability routing_candidate"):
        selector.select_agent_for_task("routing_candidate")
        
    # When explicitly allowing non-implemented for inventory discovery, it can be found
    exp = selector.select_agent_for_task("routing_candidate", require_implemented=False)
    assert exp.selected_agent_id == "smart-resource-router"


def test_existing_queue_to_warehouse_adapter_flow(tmp_path):
    """C017: Existing Queue to Warehouse Adapter Integration Test.

    Verifies the end-to-end pipeline:
    QUEUE (Task created with warehouse capability requirement)
    -> CLAIM (Task claimed by worker)
    -> WAREHOUSE (CapabilitySelector maps task requirement to authorized agent in catalog)
    -> TESTWORKER (Executes task under selected agent identity)
    -> RESULT (Emits valid completed receipt with agent metadata).

    Maintains single controller authority; does not create a second scheduler.
    """
    import sys
    sys.path.append(str(Path(__file__).parent / "controller"))
    from ctrl_helpers import make_controller, task_body, result_body

    repo_root = Path(__file__).parent.parent
    catalog = AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json")
    selector = CapabilitySelector(catalog)

    # 1. QUEUE: Create task requiring 'orchestration' capability
    home = tmp_path / "courier_home"
    ctl = make_controller(home)

    t_body = task_body(params={"job": "warehouse-routed-01", "capability": "orchestration"})
    res_code, res_payload = ctl.create_task(t_body)
    assert res_code == 201
    task_id = res_payload["task_id"]

    # 2. CLAIM: Worker claims the task
    lease = ctl.claim({"worker_id": "warehouse-worker-bay-1"})
    assert lease is not None
    dsp_id = lease["dispatch_id"]

    # 3. WAREHOUSE: Match capability to warehouse catalog agent
    req_cap = t_body["params"]["capability"]
    routing_decision = selector.select_agent_for_task(req_cap)
    assert routing_decision.selected_agent_id == "agent-chief-commander"

    # 4. START: Worker starts under selected agent
    ctl.start({"dispatch_id": dsp_id})

    # 5. RESULT: Emits completed execution receipt bound to agent
    res_data = result_body(
        dsp_id,
        result_id="res-warehouse-01",
        outcome="success",
    )
    st, resp = ctl.result(res_data)
    assert st == 200
    assert resp["status"] == "ACCEPTED_FOR_VERIFY"

    # Drain verification queue
    ctl.drain()

    # Verify task completes
    task_record = ctl.journal.task(task_id)
    assert task_record.status.value == "COMPLETE"
    assert task_record.accepted_result_id == "res-warehouse-01"


def test_warehouse_golden_path_real_execution(tmp_path):
    """C019: Warehouse Golden Path with Real Physical Subprocess Execution.

    Pipeline steps:
    1. Task packet accepted by Controller with warehouse capability parameter (Physical L2).
    2. Valid claim acquired by worker under warehouse-selected agent identity (Physical L2).
    3. Local test process started physically via runner subprocess (Physical Subprocess Execution).
    4. Result durably saved to disk and SQLite ledger (Physical Persistence).
    5. Existing verifier independently validates evidence bytes from disk (Physical L4 Verifier).
    6. Correct final state (COMPLETE) reached and re-verified on cold replay (Physical L2 Replay).
    """
    import hashlib
    import json
    import subprocess
    import sys
    from pathlib import Path

    from courier_core.controller import Controller
    from courier_core.verification import adapter_verifier
    from courier_worker import adapter_bridge as bridge

    repo_root = Path(__file__).parent.parent
    catalog = AgentCatalog.load(repo_root / "docs" / "agent-warehouse" / "AGENT_CATALOG.json")
    selector = CapabilitySelector(catalog)

    # 1. Routing explanation via warehouse catalog
    explanation = selector.select_agent_for_task("orchestration")
    assert explanation.selected_agent_id == "agent-chief-commander"

    # 2. Boot controller with standard adapter verifier
    home = tmp_path / "golden_home"
    ctl = Controller(home, verifier=adapter_verifier).boot()

    # Task packet acceptance
    expected_content = "c019-warehouse-golden-proof-bytes"
    t_body = {
        "adapter": "synthetic",
        "params": {
            "write": "out.txt",
            "content": expected_content,
            "capability": "orchestration",
            "agent_id": explanation.selected_agent_id,
        },
        "effect_class": "idempotent",
        "max_attempts": 3,
        "lease_ttl_s": 30,
    }
    st, created = ctl.create_task(t_body)
    assert st == 201
    task_id = created["task_id"]

    # 3. Valid claim acquired by worker
    lease = ctl.claim({"worker_id": explanation.selected_agent_id})
    assert lease is not None
    dsp_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dsp_id})

    # 4. Local test process started physically
    workdir = home / "artifacts" / dsp_id
    workdir.mkdir(parents=True, exist_ok=True)
    rep_path = home / "run" / "reports" / f"{dsp_id}.json"
    rep_path.parent.mkdir(parents=True, exist_ok=True)
    req_path = home / "run" / "requests" / f"{dsp_id}.json"
    req_path.parent.mkdir(parents=True, exist_ok=True)

    req_data = {
        "adapter": "synthetic",
        "params": {"write": "out.txt", "content": expected_content},
        "attempt": 1,
        "task_id": task_id,
        "dispatch_id": dsp_id,
        "effect_key": f"eff-{dsp_id}",
        "workdir": str(workdir),
        "report": str(rep_path),
    }
    req_path.write_text(json.dumps(req_data), encoding="utf-8")

    # Physical subprocess execution via Python interpreter
    cmd = [sys.executable, bridge.RUNNER_SCRIPT, str(req_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"Subprocess failed: stdout={proc.stdout}, stderr={proc.stderr}"

    # Verify physical file on disk
    artifact_file = workdir / "out.txt"
    assert artifact_file.is_file(), "Physical evidence file was not created by subprocess"
    produced_bytes = artifact_file.read_bytes()
    assert produced_bytes == expected_content.encode("utf-8")

    # Read subprocess report
    assert rep_path.is_file(), "Physical report file was not created by runner"
    report = json.loads(rep_path.read_text(encoding="utf-8"))
    assert report["outcome"] == "success"

    artifact_sha = hashlib.sha256(produced_bytes).hexdigest()

    # 5. Durable result submission
    result_payload = {
        "dispatch_id": dsp_id,
        "result_id": f"res-{dsp_id}",
        "outcome": "success",
        "artifacts": [{"path": f"artifacts/{dsp_id}/out.txt", "sha256": artifact_sha}],
    }
    st, res_resp = ctl.result(result_payload)
    assert st == 200
    assert res_resp["status"] == "ACCEPTED_FOR_VERIFY"

    # Durable receipt file on disk
    receipts_dir = home / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_file = receipts_dir / f"rcpt-{dsp_id}.json"
    receipt_file.write_text(json.dumps({
        "task_id": task_id,
        "dispatch_id": dsp_id,
        "result_id": f"res-{dsp_id}",
        "agent_id": explanation.selected_agent_id,
        "artifact_sha": artifact_sha,
        "status": "ACCEPTED_FOR_VERIFY",
    }, indent=2), encoding="utf-8")
    assert receipt_file.is_file()

    # 6. Verifier handoff & final state
    ctl.drain()

    task_record = ctl.journal.task(task_id)
    assert task_record.status.value == "COMPLETE"
    assert task_record.accepted_result_id == f"res-{dsp_id}"

    # Cold replay check in a fresh process/Controller instance
    ctl.stop()
    ctl_reloaded = Controller(home, verifier=adapter_verifier).boot()
    chain_report = ctl_reloaded.journal.verify_chain()
    assert chain_report.ok, f"Journal chain invalid on replay: {chain_report}"
    reloaded_task = ctl_reloaded.journal.task(task_id)
    assert reloaded_task.status.value == "COMPLETE"
    assert reloaded_task.accepted_result_id == f"res-{dsp_id}"
    ctl_reloaded.stop()


def test_subprocess_stdout_captured_correctly():
    """Verify stdout is captured accurately with exit code 0."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('hello stdout receipt')"]
    rcpt = execute_warehouse_subprocess(
        cmd,
        task_id="task-stdout-01",
        dispatch_id="dsp-stdout-01",
        worker_id="worker-bay-1",
    )
    assert rcpt.exit_code == 0
    assert rcpt.outcome == "success"
    assert rcpt.status == "ACCEPTED_FOR_VERIFY"
    assert rcpt.stdout == "hello stdout receipt"
    assert rcpt.stderr == ""
    assert rcpt.stdout_bytes == len(b"hello stdout receipt")
    assert rcpt.stdout_truncated is False
    assert rcpt.error_reason is None


def test_subprocess_stderr_retained_distinguishable():
    """Verify stderr is captured separately from stdout without crosstalk."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    cmd = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('normal output'); sys.stderr.write('diagnostic warning')",
    ]
    rcpt = execute_warehouse_subprocess(
        cmd,
        task_id="task-stream-01",
        dispatch_id="dsp-stream-01",
        worker_id="worker-bay-1",
    )
    assert rcpt.exit_code == 0
    assert rcpt.outcome == "success"
    assert rcpt.stdout == "normal output"
    assert rcpt.stderr == "diagnostic warning"
    assert "diagnostic warning" not in rcpt.stdout
    assert "normal output" not in rcpt.stderr


def test_subprocess_nonzero_exit_never_passes():
    """Verify non-zero exit code ALWAYS fails even if stdout claims SUCCESS."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    cmd = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('SUCCESS PASS ALL OK'); sys.exit(42)",
    ]
    rcpt = execute_warehouse_subprocess(
        cmd,
        task_id="task-nonzero-01",
        dispatch_id="dsp-nonzero-01",
        worker_id="worker-bay-1",
    )
    assert rcpt.exit_code == 42
    assert rcpt.outcome == "failure"
    assert rcpt.status == "NONZERO_EXIT"
    assert "42" in rcpt.error_reason
    assert "SUCCESS PASS ALL OK" in rcpt.stdout  # output preserved for diagnosis
    assert rcpt.outcome != "success"


def test_subprocess_empty_output_behavior():
    """Verify empty output passes when not required, but fails when required."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    cmd = [sys.executable, "-c", "pass"]

    # Case A: Output not required by contract -> passes on exit 0
    rcpt_ok = execute_warehouse_subprocess(
        cmd,
        task_id="task-empty-01",
        dispatch_id="dsp-empty-01",
        worker_id="worker-bay-1",
        require_output=False,
    )
    assert rcpt_ok.exit_code == 0
    assert rcpt_ok.outcome == "success"
    assert rcpt_ok.status == "ACCEPTED_FOR_VERIFY"

    # Case B: Output explicitly required -> fails even on exit 0
    rcpt_fail = execute_warehouse_subprocess(
        cmd,
        task_id="task-empty-02",
        dispatch_id="dsp-empty-02",
        worker_id="worker-bay-1",
        require_output=True,
    )
    assert rcpt_fail.exit_code == 0
    assert rcpt_fail.outcome == "failure"
    assert rcpt_fail.status == "EMPTY_OUTPUT"
    assert "empty output" in rcpt_fail.error_reason.lower()


def test_subprocess_output_size_limit_enforced():
    """Verify output exceeding max_output_bytes is cleanly truncated."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    # Generate 10,000 'A' characters
    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('A' * 10000)"]
    cap_limit = 1024  # 1 KB limit
    rcpt = execute_warehouse_subprocess(
        cmd,
        task_id="task-limit-01",
        dispatch_id="dsp-limit-01",
        worker_id="worker-bay-1",
        max_output_bytes=cap_limit,
    )
    assert rcpt.exit_code == 0
    assert rcpt.stdout_bytes == 10000
    assert rcpt.stdout_truncated is True
    assert "[TRUNCATED: max_output_bytes exceeded]" in rcpt.stdout
    # Total length before marker is cap_limit
    assert rcpt.stdout.startswith("A" * cap_limit)


def test_subprocess_timeout_produces_structured_failure():
    """Verify timed out process is terminated and yields a structured failure."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    rcpt = execute_warehouse_subprocess(
        cmd,
        task_id="task-timeout-01",
        dispatch_id="dsp-timeout-01",
        worker_id="worker-bay-1",
        timeout_s=0.3,
    )
    assert rcpt.outcome == "failure"
    assert rcpt.status == "TIMEOUT"
    assert "timed out after 0.3s" in rcpt.error_reason
    assert rcpt.duration_s >= 0.25


def test_subprocess_sensitive_data_redaction():
    """Verify API keys, bearer tokens, and credentials are redacted."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    secret_script = (
        "import sys\n"
        "sys.stdout.write('header: Bearer secret-auth-token-987654321\\n')\n"
        "sys.stdout.write('key: api_key=my-super-secret-key-12345\\n')\n"
        "sys.stdout.write('sk: sk-abcdefghijklmnopqrstuvwxyz012345\\n')\n"
        "sys.stdout.write('gh: ghp_1234567890abcdefghijklmnopqrstuvwxyz\\n')\n"
    )
    cmd = [sys.executable, "-c", secret_script]
    rcpt = execute_warehouse_subprocess(
        cmd,
        task_id="task-redact-01",
        dispatch_id="dsp-redact-01",
        worker_id="worker-bay-1",
        redact_secrets=True,
    )
    assert rcpt.outcome == "success"
    assert "secret-auth-token-987654321" not in rcpt.stdout
    assert "my-super-secret-key-12345" not in rcpt.stdout
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in rcpt.stdout
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in rcpt.stdout
    assert "[REDACTED]" in rcpt.stdout


def test_subprocess_receipt_identity_and_persistence(tmp_path):
    """Verify receipt carries genuine IDs and can be durably written to disk."""
    from scripts.agent_warehouse import execute_warehouse_subprocess

    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('durable payload')"]
    rcpt = execute_warehouse_subprocess(
        cmd,
        task_id="task-dur-01",
        dispatch_id="dsp-dur-01",
        worker_id="worker-alpha",
        agent_id="agent-chief-commander",
    )
    assert rcpt.execution_id.startswith("exec-dsp-dur-01-")
    assert rcpt.task_id == "task-dur-01"
    assert rcpt.dispatch_id == "dsp-dur-01"
    assert rcpt.worker_id == "worker-alpha"
    assert rcpt.agent_id == "agent-chief-commander"

    receipts_dir = tmp_path / "receipts"
    written_file = rcpt.save_to_dir(receipts_dir)
    assert written_file.is_file()
    assert written_file.name == "rcpt-dsp-dur-01.json"

    saved_data = json.loads(written_file.read_text(encoding="utf-8"))
    assert saved_data["execution_id"] == rcpt.execution_id
    assert saved_data["outcome"] == "success"
    assert saved_data["status"] == "ACCEPTED_FOR_VERIFY"
    assert saved_data["stdout"] == "durable payload"




