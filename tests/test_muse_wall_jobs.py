"""Job assignment for the Windows Muse Wall: Slot NN <- Job NN.

Covers the supervisor job extension (assign/run/status). Every test job
carries a UNIQUE generated print snippet (never 32 identical jobs); real
commands stay behind the real_jobs_enabled gate and are never guessed.
"""
import copy
import sys
import time
from pathlib import Path

from scripts.windows_muse_wall.supervisor import MuseWallSupervisor


BASE_CONFIG = {
    "desired_slots": 64,
    "active_limit": 32,
    "provider_launch_enabled": False,
    "staged_levels": [1, 4, 8, 16, 32, 64],
    "minimum_free_memory_mb": 2500,
}


def wall(tmp_path, **overrides):
    config = copy.deepcopy(BASE_CONFIG)
    config.update(overrides)
    supervisor = MuseWallSupervisor(tmp_path, config)
    supervisor.initialize()
    return supervisor


def test_assign_all_test_maps_slot_to_job_one_to_one(tmp_path):
    supervisor = wall(tmp_path)
    results = supervisor.assign_all_test(32)
    assert len(results) == 32
    assert all(item["assigned"] is True for item in results)
    for index in range(1, 33):
        job = supervisor.job_path(f"MUSE-{index:02d}")
        assert job.is_file()


def test_test_job_commands_are_unique_never_identical(tmp_path):
    supervisor = wall(tmp_path)
    supervisor.assign_all_test(32)
    commands = set()
    for index in range(1, 33):
        slot_id = f"MUSE-{index:02d}"
        job_id = f"JOB-{index:02d}"
        job = supervisor.job_status(slot_id)["job"]
        assert job["job_id"] == job_id
        assert job["slot_id"] == slot_id
        assert job["kind"] == "test"
        assert job["status"] == "ASSIGNED"
        snippet = job["command"][2]
        assert job_id in snippet and slot_id in snippet
        commands.add(snippet)
    assert len(commands) == 32


def test_job_files_are_isolated_per_slot(tmp_path):
    supervisor = wall(tmp_path)
    supervisor.assign_all_test(32)
    paths = {supervisor.job_path(f"MUSE-{i:02d}") for i in range(1, 33)}
    assert len(paths) == 32


def test_assign_rejects_slot_job_mismatch(tmp_path):
    supervisor = wall(tmp_path)
    outcome = supervisor.assign_job("MUSE-01", "JOB-02")
    assert outcome["assigned"] is False
    assert outcome["reason"] == "slot_job_mismatch"
    assert not supervisor.job_path("MUSE-01").exists()


def test_assign_refuses_to_clobber_pending_job(tmp_path):
    supervisor = wall(tmp_path)
    assert supervisor.assign_job("MUSE-01", "JOB-01")["assigned"] is True
    outcome = supervisor.assign_job("MUSE-01", "JOB-01")
    assert outcome["assigned"] is False
    assert outcome["reason"] == "job_pending"
    assert supervisor.assign_job("MUSE-01", "JOB-01", overwrite=True)["assigned"] is True


def test_run_without_job_is_denied(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True)
    outcome = supervisor.run_job("MUSE-01")
    assert outcome["started"] is False
    assert outcome["reason"] == "no_job_assigned"


def test_run_test_job_respects_provider_gate(tmp_path):
    supervisor = wall(tmp_path)
    supervisor.assign_job("MUSE-01", "JOB-01")
    outcome = supervisor.run_job("MUSE-01")
    assert outcome["started"] is False
    assert outcome["reason"] == "provider_launch_disabled"


def test_run_test_job_writes_unique_log_and_reaps_done(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True, active_limit=32)
    supervisor.assign_job("MUSE-01", "JOB-01")
    outcome = supervisor.run_job("MUSE-01")
    assert outcome["started"] is True
    log = supervisor.job_log_path("MUSE-01", "JOB-01")
    for _ in range(50):
        status = supervisor.job_status("MUSE-01")
        if status["job"]["status"] == "DONE":
            break
        time.sleep(0.1)
    status = supervisor.job_status("MUSE-01")
    assert status["job"]["status"] == "DONE"
    assert status["slot_state"] == "DONE"
    assert supervisor.status()["states"].get("CRASHED", 0) == 0
    assert "JOB-01 on MUSE-01 OK" in log.read_text(encoding="utf-8", errors="replace")


def test_run_refuses_tampered_test_template(tmp_path):
    from scripts.windows_muse_wall.slot_state import atomic_write, read_json

    supervisor = wall(tmp_path, provider_launch_enabled=True)
    supervisor.assign_job("MUSE-01", "JOB-01")
    job_path = supervisor.job_path("MUSE-01")
    job = read_json(job_path)
    job["command"] = [sys.executable, "-c", "print('forged')"]
    atomic_write(job_path, job)
    outcome = supervisor.run_job("MUSE-01")
    assert outcome["started"] is False
    assert outcome["reason"] == "test_template_mismatch"


def test_real_job_requires_gate_and_explicit_command(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True)
    assert supervisor.assign_job("MUSE-01", "JOB-01", kind="real")["assigned"] is True
    outcome = supervisor.run_job("MUSE-01")
    assert outcome["started"] is False
    assert outcome["reason"] == "real_jobs_disabled"
    supervisor.config["real_jobs_enabled"] = True
    outcome = supervisor.run_job("MUSE-01")
    assert outcome["started"] is False
    assert outcome["reason"] == "no_launch_command"


def test_assign_never_launches_a_process(tmp_path):
    supervisor = wall(tmp_path, provider_launch_enabled=True)
    supervisor.assign_all_test(4)
    for index in range(1, 5):
        slot = supervisor.load_slot(f"MUSE-{index:02d}")
        assert slot["process"] is None
        assert slot["state"] == "READY"
