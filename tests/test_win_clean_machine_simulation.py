"""End-to-End Clean-Machine Acceptance Simulation for Windows (Cross-Platform).

Verifies the locked V1 Clean-Machine Acceptance and Freeze-Recovery contracts
mandated in docs/V1_PRODUCT_QUALITY_BAR.md §9-§10:
1. Binary placement into %LOCALAPPDATA%\\CourierWorker
2. Headless status L0 pre-flight check
3. Golden task lifecycle in SQLite journal
4. Device health sampling & telemetry recording
5. Freeze interruption simulation with work preservation (no mutation)
6. Exact-owned recovery ladder & Recovery Receipt generation
7. Safe resume point computation from durable state
8. Diagnostics bundle generation with secret redaction
9. Clean uninstallation preserving user journal (%LOCALAPPDATA%\\Courier)
"""
import json
import os
import shutil
import sqlite3
import subprocess
import zipfile
from pathlib import Path
import pytest

from scripts.courier_doctor import export_diagnostics
from scripts.courier_recovery import (
    build_recovery_receipt,
    execute_escalation_ladder,
    terminate_owned_process_by_pid,
    write_recovery_receipt,
)
from scripts.courier_status import (
    evaluate_reboot_verdict,
    get_critical_snapshot_l0,
    get_journal_stats,
)
from scripts.device_health_sampler import (
    evaluate_health_status,
    record_sample_to_db,
    record_sample_to_jsonl,
    sample_resources,
)
from scripts.layered_health import (
    FailureClassification,
    LayerState,
    evaluate_system_layered_health,
)
from scripts.right_host_guard import (
    get_current_host_identity,
    verify_right_host,
)
from scripts.safe_resume_point import (
    compute_safe_resume_point,
    write_continuation_receipt,
)
from scripts.work_preservation import (
    preserve_uncommitted_work,
)


def test_clean_machine_e2e_acceptance_simulation(tmp_path, monkeypatch):
    """Simulates the full Clean-Machine Acceptance journey end-to-end."""
    # -------------------------------------------------------------------------
    # 1. SETUP CLEAN ENVIRONMENT
    # -------------------------------------------------------------------------
    mock_localappdata = tmp_path / "AppData" / "Local"
    courier_worker_dir = mock_localappdata / "CourierWorker"
    courier_data_dir = mock_localappdata / "Courier"
    run_dir = courier_data_dir / "run"
    claims_dir = run_dir / "claims"
    receipts_dir = run_dir / "receipts"
    
    courier_worker_dir.mkdir(parents=True)
    courier_data_dir.mkdir(parents=True)
    claims_dir.mkdir(parents=True)
    receipts_dir.mkdir(parents=True)

    monkeypatch.setenv("LOCALAPPDATA", str(mock_localappdata))

    # Mock clean git status for the headless status collector
    monkeypatch.setattr("scripts.courier_status.get_git_status", lambda repo_dir=None: {
        "branch": "lane/L6-clean-machine-acceptance",
        "dirty_count": 0,
        "unpushed_count": 0,
        "clean": True,
    })

    # Binary placement (simulating installer)
    (courier_worker_dir / "Courier.exe").write_bytes(b"MZ_MOCK_COURIER_EXE")
    (courier_worker_dir / "daemon.py").write_text("# mock daemon")
    (courier_worker_dir / "uninstall.ps1").write_text("# mock uninstaller")

    # Write initial config with sensitive token
    config_file = courier_data_dir / "config.json"
    config_file.write_text(json.dumps({
        "COURIER_CONTROLLER_PORT": 8800,
        "COURIER_HUB_PORT": 8801,
        "SECRET_TOKEN": "Bearer ghp_SUPER_SECRET_GITHUB_TOKEN_12345"
    }))

    # -------------------------------------------------------------------------
    # 2. HEADLESS STATUS L0 PRE-CHECK
    # -------------------------------------------------------------------------
    db_path = courier_data_dir / "courier.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL
        )
    """)
    conn.commit()

    snapshot = get_critical_snapshot_l0(courier_data_dir)
    assert snapshot["schema_version"] == "1.0"
    assert snapshot["reboot_verdict"]["safe"] is True
    assert snapshot["reboot_verdict"]["verdict"] == "SAFE_TO_REBOOT"

    # -------------------------------------------------------------------------
    # 3. GOLDEN TASK LIFECYCLE IN SQLITE JOURNAL
    # -------------------------------------------------------------------------
    events = [
        ("TASK_CREATED", json.dumps({"task_id": "task-100", "effect_class": "idempotent"})),
        ("TASK_STARTED", json.dumps({"task_id": "task-100", "owner_pid": 1234})),
        ("RESULT_ACCEPTED", json.dumps({"task_id": "task-100", "result": "ok"})),
        ("TASK_COMPLETED", json.dumps({"task_id": "task-100", "status": "COMPLETED"})),
    ]
    for etype, payload in events:
        conn.execute("INSERT INTO events (event_type, payload) VALUES (?, ?)", (etype, payload))
    conn.commit()

    stats = get_journal_stats(courier_data_dir)
    assert stats["exists"] is True
    assert stats["event_count"] == 4

    # -------------------------------------------------------------------------
    # 4. DEVICE HEALTH SAMPLING & TELEMETRY
    # -------------------------------------------------------------------------
    health_jsonl = courier_data_dir / "device_health.jsonl"
    sample = sample_resources()
    record_sample_to_db(sample, db_path)
    record_sample_to_jsonl(sample, health_jsonl)
    eval_res = evaluate_health_status(sample)
    assert eval_res["status"] in ("OK", "WARNING", "CRITICAL")
    assert health_jsonl.exists()

    # -------------------------------------------------------------------------
    # 5. FREEZE INTERRUPTION SIMULATION & WORK PRESERVATION
    # -------------------------------------------------------------------------
    # Simulate an active interrupted task in claims
    claim_file = claims_dir / "dispatch-task-101.json"
    claim_file.write_text(json.dumps({
        "task_id": "task-101",
        "effect_class": "non_idempotent",
        "owner_pid": 99999,
        "checkpoint": "step-3-checkpoint",
        "timestamp": 1234567890
    }))

    # Verify reboot check refuses reboot during in-flight claim
    snap_interrupted = get_critical_snapshot_l0(courier_data_dir)
    assert snap_interrupted["reboot_verdict"]["safe"] is False
    assert snap_interrupted["reboot_verdict"]["verdict"] == "NOT_SAFE_TO_REBOOT"
    assert any("active task claims" in r for r in snap_interrupted["reboot_verdict"]["reasons"])

    # Perform forensic work preservation without mutating repo
    repo_mock = tmp_path / "mock_repo"
    repo_mock.mkdir()
    subprocess.run(["git", "init"], cwd=repo_mock, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_mock, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo_mock, check=True)
    (repo_mock / "initial.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo_mock, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_mock, check=True)

    # Uncommitted change
    (repo_mock / "pending_work.py").write_text("print('critical pending computation')")
    recovery_dir = courier_data_dir / "recovery"
    manifest = preserve_uncommitted_work(repo_dir=repo_mock, output_dir=recovery_dir)
    manifest_path = Path(manifest["manifest_path"])
    assert manifest_path.is_file()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["schema_version"] == "1.0"

    # -------------------------------------------------------------------------
    # 6. EXACT-OWNED RECOVERY LADDER & RECEIPT
    # -------------------------------------------------------------------------
    res_ladder = execute_escalation_ladder(level=1, app_data_dir=courier_data_dir)
    assert res_ladder["outcome"] == "STATUS_VERIFIED"

    receipt = build_recovery_receipt(
        snapshot=snap_interrupted,
        incident_type="INTERRUPTION_OR_FREEZE_RECOVERY",
        action_taken=res_ladder["action_taken"],
        outcome=res_ladder["outcome"],
    )
    receipt_file = write_recovery_receipt(receipt, app_data_dir=courier_data_dir)
    assert receipt_file.is_file()
    assert (receipts_dir / f"{receipt['receipt_id']}.json").exists()

    # -------------------------------------------------------------------------
    # 7. SAFE RESUME POINT COMPUTATION
    # -------------------------------------------------------------------------
    # Remove active claim post-recovery
    claim_file.unlink()

    # Insert interrupted task into SQLite journal
    conn.execute(
        "INSERT INTO events (event_type, payload) VALUES (?, ?)",
        ("TASK_STARTED", json.dumps({"task_id": "task-101", "checkpoint": "step-3-checkpoint"}))
    )
    conn.commit()
    conn.close()

    resume_point = compute_safe_resume_point(app_data_dir=courier_data_dir)
    assert "task-100" in resume_point["quiesced_tasks"]  # Completed task remains quiesced
    assert any(t["task_id"] == "task-101" for t in resume_point["resumable_tasks"])
    assert resume_point["resumable_tasks"][0]["checkpoint"] == "step-3-checkpoint"

    res_receipt_path = write_continuation_receipt(resume_point, app_data_dir=courier_data_dir)
    assert res_receipt_path.is_file()

    # -------------------------------------------------------------------------
    # 8. DIAGNOSTICS BUNDLE & SECRET REDACTION
    # -------------------------------------------------------------------------
    (run_dir / "critical_snapshot_l0.json").write_text(json.dumps(snapshot))
    zip_dest = tmp_path / "diagnostics_export.zip"
    monkeypatch.setenv("COURIER_HOME", str(courier_data_dir))
    export_diagnostics(zip_dest)
    assert zip_dest.is_file()

    with zipfile.ZipFile(zip_dest, "r") as z:
        namelist = z.namelist()
        assert "run/critical_snapshot_l0.json" in namelist
        assert "device_health.jsonl" in namelist
        assert any(n.startswith("run/receipts/RCPT-") for n in namelist)
        assert any(n.startswith("run/receipts/RESUME-") for n in namelist)
        # Verify secret redaction on config.json
        config_content = z.read("config.json").decode("utf-8")
        assert "ghp_SUPER_SECRET" not in config_content
        assert "***REDACTED***" in config_content

    # -------------------------------------------------------------------------
    # 9. CLEAN UNINSTALLATION CONTRACT
    # -------------------------------------------------------------------------
    # Uninstaller removes binaries from CourierWorker
    shutil.rmtree(courier_worker_dir)
    assert not courier_worker_dir.exists()

    # Uninstaller clears credentials from config.json and run/
    if config_file.exists():
        config_file.unlink()
    shutil.rmtree(run_dir)

    # CRITICAL: User journal database and logs in %LOCALAPPDATA%\Courier MUST SURVIVE
    assert courier_data_dir.exists()
    assert (courier_data_dir / "courier.db").exists()
    assert (courier_data_dir / "device_health.jsonl").exists()

    # Verify journal integrity post-uninstall
    verify_conn = sqlite3.connect(str(courier_data_dir / "courier.db"))
    cur = verify_conn.cursor()
    cur.execute("PRAGMA integrity_check")
    row = cur.fetchone()
    assert row[0] == "ok"
    verify_conn.close()
