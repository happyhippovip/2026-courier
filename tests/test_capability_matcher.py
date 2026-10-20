import os
import json
import pytest
from pathlib import Path
from courier_core.capability_matcher import (
    WorkerCapabilities,
    TaskRequirements,
    MatchResult,
    match_capabilities,
    CapabilityRegistry,
)


def test_exact_os_and_arch_matching():
    worker = WorkerCapabilities(
        worker_id="win-node-1",
        os="windows",
        arch="x86_64",
        tags={"sandbox": True},
        supported_providers=["local", "mock"],
    )

    # Matching requirement
    req_match = TaskRequirements(
        work_item_id="task-1",
        required_os="windows",
        required_arch="x86_64",
    )
    res = match_capabilities(worker, req_match)
    assert res.matched is True
    assert res.score > 0

    # Mismatched OS
    req_os_mismatch = TaskRequirements(
        work_item_id="task-2",
        required_os="linux",
    )
    res_os = match_capabilities(worker, req_os_mismatch)
    assert res_os.matched is False
    assert any("OS mismatch" in r for r in res_os.reasons)

    # Mismatched Arch
    req_arch_mismatch = TaskRequirements(
        work_item_id="task-3",
        required_arch="arm64",
    )
    res_arch = match_capabilities(worker, req_arch_mismatch)
    assert res_arch.matched is False
    assert any("Architecture mismatch" in r for r in res_arch.reasons)


def test_required_tags_and_forbidden_tags():
    worker = WorkerCapabilities(
        worker_id="win-node-2",
        os="windows",
        arch="x86_64",
        tags={
            "csharp": True,
            "headless": True,
            "gpu": True,
            "tier": "enterprise",
        },
        supported_providers=["local"],
    )

    # Required tags satisfied
    req_pass = TaskRequirements(
        work_item_id="task-pass",
        required_tags={"csharp": True, "tier": "enterprise"},
    )
    res_pass = match_capabilities(worker, req_pass)
    assert res_pass.matched is True

    # Required tag missing or wrong value
    req_missing_tag = TaskRequirements(
        work_item_id="task-fail-tag",
        required_tags={"docker": True},
    )
    res_missing = match_capabilities(worker, req_missing_tag)
    assert res_missing.matched is False
    assert any("Missing required tag 'docker'" in r for r in res_missing.reasons)

    # Forbidden tag present
    req_forbidden = TaskRequirements(
        work_item_id="task-forbidden",
        forbidden_tags=["gpu"],
    )
    res_forbidden = match_capabilities(worker, req_forbidden)
    assert res_forbidden.matched is False
    assert any("Forbidden tag 'gpu' is present" in r for r in res_forbidden.reasons)


def test_numeric_constraints():
    worker = WorkerCapabilities(
        worker_id="heavy-node",
        os="linux",
        arch="x86_64",
        tags={
            "memory_mb": 16384,
            "cpu_cores": 8,
            "current_load": 0.25,
        },
        supported_providers=["local"],
    )

    # Valid constraints
    req_valid = TaskRequirements(
        work_item_id="heavy-task",
        min_memory_mb=8192,
        min_cpu_cores=4,
        max_load=0.80,
    )
    res_valid = match_capabilities(worker, req_valid)
    assert res_valid.matched is True

    # Memory too low
    req_insufficient_mem = TaskRequirements(
        work_item_id="huge-task",
        min_memory_mb=32768,
    )
    res_mem = match_capabilities(worker, req_insufficient_mem)
    assert res_mem.matched is False
    assert any("Insufficient memory" in r for r in res_mem.reasons)

    # Load too high
    worker_busy = WorkerCapabilities(
        worker_id="busy-node",
        os="linux",
        arch="x86_64",
        tags={"memory_mb": 16384, "current_load": 0.95},
        supported_providers=["local"],
    )
    res_busy = match_capabilities(worker_busy, req_valid)
    assert res_busy.matched is False
    assert any("Load exceeds limit" in r for r in res_busy.reasons)


def test_supported_providers():
    worker = WorkerCapabilities(
        worker_id="provider-node",
        os="windows",
        arch="x86_64",
        tags={},
        supported_providers=["mock", "gemini-flash"],
    )

    req_ok = TaskRequirements(
        work_item_id="task-prov-ok",
        required_provider="gemini-flash",
    )
    res_ok = match_capabilities(worker, req_ok)
    assert res_ok.matched is True

    req_bad = TaskRequirements(
        work_item_id="task-prov-bad",
        required_provider="anthropic-sonnet",
    )
    res_bad = match_capabilities(worker, req_bad)
    assert res_bad.matched is False
    assert any("Provider 'anthropic-sonnet' not supported" in r for r in res_bad.reasons)


def test_registry_worker_selection_and_ranking():
    registry = CapabilityRegistry()

    w1 = WorkerCapabilities(
        worker_id="w-slow",
        os="windows",
        arch="x86_64",
        tags={"memory_mb": 8192, "current_load": 0.70},
        supported_providers=["local"],
    )
    w2 = WorkerCapabilities(
        worker_id="w-fast",
        os="windows",
        arch="x86_64",
        tags={"memory_mb": 32768, "current_load": 0.10, "csharp": True},
        supported_providers=["local"],
    )
    w3 = WorkerCapabilities(
        worker_id="w-linux",
        os="linux",
        arch="x86_64",
        tags={"memory_mb": 65536, "current_load": 0.05},
        supported_providers=["local"],
    )

    registry.register(w1)
    registry.register(w2)
    registry.register(w3)

    req = TaskRequirements(
        work_item_id="build-cs",
        required_os="windows",
        required_tags={"csharp": True},
        min_memory_mb=16384,
    )

    candidates = registry.find_matching_workers(req)
    assert len(candidates) == 1
    assert candidates[0].worker.worker_id == "w-fast"

    # General windows task: both w1 and w2 match, w2 should rank higher due to lower load & higher capacity
    req_general = TaskRequirements(
        work_item_id="general-win",
        required_os="windows",
    )
    general_candidates = registry.find_matching_workers(req_general)
    assert len(general_candidates) == 2
    assert general_candidates[0].worker.worker_id == "w-fast"
    assert general_candidates[1].worker.worker_id == "w-slow"
    assert general_candidates[0].score > general_candidates[1].score


def test_cli_invocation(tmp_path):
    worker_file = tmp_path / "worker.json"
    worker_file.write_text(
        json.dumps({
            "worker_id": "cli-win",
            "os": "windows",
            "arch": "x86_64",
            "tags": {"memory_mb": 16384, "csharp": True},
            "supported_providers": ["local"]
        }),
        encoding="utf-8"
    )

    task_file = tmp_path / "task.json"
    task_file.write_text(
        json.dumps({
            "work_item_id": "cli-task",
            "required_os": "windows",
            "required_tags": {"csharp": True},
            "min_memory_mb": 8192
        }),
        encoding="utf-8"
    )

    import subprocess
    import sys

    # Match via CLI
    cmd = [
        sys.executable,
        "-m",
        "courier_core.capability_matcher",
        "match",
        "--worker",
        str(worker_file),
        "--task",
        str(task_file),
    ]
    root = str(Path(__file__).resolve().parent.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = root
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=root, env=env)
    out = json.loads(proc.stdout)
    assert out["matched"] is True
    assert out["score"] > 0
