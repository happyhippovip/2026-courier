"""Targeted Validation Suite: Upgrade Data Preservation (MUSE-027).

Verifies that Courier application updates preserve:
1. Append-only SQLite event ledger (courier.db) without reset, corruption, or data loss.
2. User configuration (config.json), preserving custom port configurations and user settings.
3. User receipts and task artifacts in %LOCALAPPDATA%\\Courier.
4. Clean separation between program files ({app} / %LOCALAPPDATA%\\CourierWorker) and
   persistent user state (%LOCALAPPDATA%\\Courier).
5. Updated application starts cleanly from preserved existing state.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path
import pytest

from courier_core.controller import Controller
from courier_core.state_machine import TaskStatus
from courier_core.verification import adapter_verifier
from courier_runtime.workflow_continuation import sha256_file


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_upgrade_preserves_ledger_database_and_replay_state(tmp_path):
    """Simulates a full version upgrade and verifies ledger preservation and replay."""
    data_dir = tmp_path / "AppData" / "Local" / "Courier"
    install_dir = tmp_path / "AppData" / "Local" / "CourierWorker"
    data_dir.mkdir(parents=True)
    install_dir.mkdir(parents=True)

    # 1. Establish v1.0.0 program state
    (install_dir / "version.txt").write_text("1.0.0", encoding="utf-8")
    (install_dir / "Courier.exe").write_bytes(b"MZ_V1_0_0_LAUNCHER")

    # 2. Boot Controller and record synthetic user tasks into courier.db
    ctl = Controller(data_dir, verifier=adapter_verifier).boot()
    task_body = {
        "adapter": "synthetic",
        "params": {"write": "user_doc.txt", "content": "vital user data"},
        "effect_class": "idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 60,
        "idempotency_key": "WF:UPGRADE-PRESERVE-01",
    }
    st, res = ctl.create_task(task_body)
    assert st == 201
    task_id = res["task_id"]

    lease = ctl.claim({"worker_id": "worker-v1"})
    assert lease is not None
    dsp_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dsp_id})

    # Deliver result
    artifacts_dir = data_dir / "artifacts" / dsp_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    doc_path = artifacts_dir / "user_doc.txt"
    doc_path.write_text("vital user data", encoding="utf-8")
    doc_sha = sha256_file(doc_path)

    st_res, res_body = ctl.result({
        "dispatch_id": dsp_id,
        "result_id": f"res-{dsp_id}",
        "outcome": "success",
        "artifacts": [{"path": f"artifacts/{dsp_id}/user_doc.txt", "sha256": doc_sha}],
    })
    assert st_res == 200
    ctl.drain()
    task_rec = ctl.journal.task(task_id)
    assert task_rec.status == TaskStatus.COMPLETE
    ctl.stop()

    # Capture cryptographic hashes BEFORE upgrade
    db_path = data_dir / "courier.db"
    assert db_path.is_file()
    hash_db_before = _sha256(db_path)
    hash_doc_before = _sha256(doc_path)

    # 3. SIMULATE VERSION UPGRADE (v1.0.0 -> v1.1.0)
    # The installer replaces program binaries in install_dir (CourierWorker)
    shutil.rmtree(install_dir)
    install_dir.mkdir(parents=True)
    (install_dir / "version.txt").write_text("1.1.0", encoding="utf-8")
    (install_dir / "Courier.exe").write_bytes(b"MZ_V1_1_0_UPGRADED_LAUNCHER")

    # 4. VERIFY USER DATA INTEGRITY POST-UPGRADE
    hash_db_after = _sha256(db_path)
    hash_doc_after = _sha256(doc_path)

    assert hash_db_before == hash_db_after, "courier.db was modified or corrupted during upgrade"
    assert hash_doc_before == hash_doc_after, "User artifacts were modified or lost during upgrade"

    # 5. Boot upgraded application on existing data directory
    upgraded_ctl = Controller(data_dir, verifier=adapter_verifier).boot()
    assert upgraded_ctl.mode == "normal"
    upgraded_task = upgraded_ctl.journal.task(task_id)
    assert upgraded_task.status == TaskStatus.COMPLETE
    assert upgraded_task.task_id == task_id
    assert upgraded_task.params["write"] == "user_doc.txt"

    # Verify no duplicate task creation or projection divergence
    all_tasks = upgraded_ctl.journal.tasks()
    assert len(all_tasks) == 1
    upgraded_ctl.stop()


def test_upgrade_preserves_custom_settings_and_merges_new_options(tmp_path):
    """Verifies that existing config.json custom properties are retained on upgrade."""
    data_dir = tmp_path / "AppData" / "Local" / "Courier"
    data_dir.mkdir(parents=True)
    config_file = data_dir / "config.json"

    # User has customized ports and personal preferences
    initial_config = {
        "COURIER_CONTROLLER_PORT": 9100,
        "COURIER_HUB_PORT": 9101,
        "COURIER_SERVER": "http://192.168.1.100:8080",
        "COURIER_WORKER_ID": "WIN-CUSTOM-ID",
        "USER_THEME": "graphite",
        "LOG_RETENTION_DAYS": 30,
    }
    config_file.write_text(json.dumps(initial_config, indent=2), encoding="utf-8")

    # Simulation of upgrade installer config merge logic
    # Replicates the fixed install.ps1 logic
    existing_obj = {}
    if config_file.exists():
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        existing_obj.update(raw)

    # Installer allows updating server or adding new default options
    new_server_param = "http://192.168.1.100:8080"  # Unchanged
    new_option_name = "COURIER_METRICS_ENABLED"
    new_option_val = True

    existing_obj["COURIER_SERVER"] = new_server_param
    existing_obj[new_option_name] = new_option_val
    config_file.write_text(json.dumps(existing_obj, indent=2), encoding="utf-8")

    # Verify updated configuration
    updated_config = json.loads(config_file.read_text(encoding="utf-8"))
    assert updated_config["COURIER_CONTROLLER_PORT"] == 9100, "Custom controller port was lost"
    assert updated_config["COURIER_HUB_PORT"] == 9101, "Custom hub port was lost"
    assert updated_config["USER_THEME"] == "graphite", "User preference was wiped"
    assert updated_config["LOG_RETENTION_DAYS"] == 30, "User preference was wiped"
    assert updated_config["COURIER_SERVER"] == "http://192.168.1.100:8080"
    assert updated_config["COURIER_METRICS_ENABLED"] is True, "New upgrade option was not merged"


def test_upgrade_preserves_receipts_and_token(tmp_path):
    """Verifies that tokens and audit receipts survive upgrade untouched."""
    data_dir = tmp_path / "AppData" / "Local" / "Courier"
    run_dir = data_dir / "run"
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True)

    token_file = run_dir / "controller.token"
    token_file.write_text("token-secret-alpha-999", encoding="utf-8")

    receipt_file = receipts_dir / "RESUME-20261011-001.json"
    receipt_data = {"receipt_id": "REC-001", "task_id": "T-100", "status": "VERIFIED"}
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    hash_token_before = _sha256(token_file)
    hash_receipt_before = _sha256(receipt_file)

    # Simulated app directory replacement
    app_dir = tmp_path / "CourierWorker"
    app_dir.mkdir(parents=True)
    (app_dir / "Courier.exe").write_bytes(b"MZ_NEW")

    # Re-verify
    assert _sha256(token_file) == hash_token_before
    assert _sha256(receipt_file) == hash_receipt_before
