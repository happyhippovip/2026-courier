"""Tests for Pipeline Orchestrator for Real A to B to C Handoffs."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.pipeline_orchestrator import (
    PipelineOrchestrator,
    PipelineResult,
    StageReceipt,
    run_abc_pipeline,
    main,
)


def test_full_chain_dispatch_workerA_handoff_workerB_verifier_done(tmp_path):
    secret = "pipeline-secret-2026"
    orchestrator = PipelineOrchestrator(secret_key=secret, out_dir=str(tmp_path))

    def worker_a(input_data: dict) -> dict:
        return {"code_generated": "def add(x, y): return x + y", "stage": "A"}

    def worker_b(stage_a_output: dict) -> dict:
        code = stage_a_output["code_generated"]
        return {"test_generated": f"assert {code.splitlines()[0][4:7]}(1, 2) == 3", "stage": "B"}

    def verifier(stage_a_output: dict, stage_b_output: dict) -> bool:
        # Independent validation
        return "def add" in stage_a_output["code_generated"] and "assert" in stage_b_output["test_generated"]

    result = orchestrator.execute(
        item_id="task_abc_success",
        worker_a_fn=worker_a,
        worker_b_fn=worker_b,
        verifier_fn=verifier,
    )

    assert result.status == "DONE"
    assert result.is_verified is True
    assert len(result.stage_receipts) == 3
    assert result.stage_receipts["worker_a"].signature.startswith("hmac-sha256:")
    assert result.stage_receipts["worker_b"].signature.startswith("hmac-sha256:")
    assert result.stage_receipts["verifier"].signature.startswith("hmac-sha256:")


def test_worker_a_failure_aborts_pipeline(tmp_path):
    orchestrator = PipelineOrchestrator(secret_key="secret", out_dir=str(tmp_path))
    worker_b_called = False

    def failing_worker_a(input_data: dict):
        raise RuntimeError("Worker A crashed during code generation")

    def worker_b(stage_a_output: dict):
        nonlocal worker_b_called
        worker_b_called = True
        return {}

    result = orchestrator.execute(
        item_id="task_fail_a",
        worker_a_fn=failing_worker_a,
        worker_b_fn=worker_b,
        verifier_fn=lambda a, b: True,
    )

    assert result.status == "FAILED_STAGE_A"
    assert worker_b_called is False
    assert result.is_verified is False
    assert "Worker A crashed" in result.error_message


def test_corrupt_handoff_receipt_rejected(tmp_path):
    orchestrator = PipelineOrchestrator(secret_key="secret", out_dir=str(tmp_path))

    def worker_a(input_data: dict):
        return {"data": "authentic-a"}

    def tampered_handoff_hook(receipt: StageReceipt):
        # Tamper payload before Worker B reads it
        receipt.payload["data"] = "tampered-content"

    result = orchestrator.execute(
        item_id="task_tamper",
        worker_a_fn=worker_a,
        worker_b_fn=lambda a: {"data": "b"},
        verifier_fn=lambda a, b: True,
        stage_a_post_hook=tampered_handoff_hook,
    )

    assert result.status == "HANDOFF_VERIFICATION_FAILED"
    assert result.is_verified is False


def test_verifier_detects_bad_artifact_and_blocks_done(tmp_path):
    orchestrator = PipelineOrchestrator(secret_key="secret", out_dir=str(tmp_path))

    def worker_a(input_data: dict):
        return {"syntax_valid": False}

    def worker_b(stage_a: dict):
        return {"tests_passed": False}

    def verifier(stage_a: dict, stage_b: dict) -> bool:
        # Rejects if syntax is invalid or tests failed
        return stage_a.get("syntax_valid", False) and stage_b.get("tests_passed", False)

    result = orchestrator.execute(
        item_id="task_verifier_reject",
        worker_a_fn=worker_a,
        worker_b_fn=worker_b,
        verifier_fn=verifier,
    )

    assert result.status == "VERIFICATION_FAILED"
    assert result.is_verified is False
    assert "Verifier rejected" in result.error_message


def test_evidence_aggregation_in_final_receipt(tmp_path):
    orchestrator = PipelineOrchestrator(secret_key="secret", out_dir=str(tmp_path))

    result = orchestrator.execute(
        item_id="task_evidence",
        worker_a_fn=lambda inp: {"a": 1},
        worker_b_fn=lambda a: {"b": 2},
        verifier_fn=lambda a, b: True,
    )

    assert result.status == "DONE"
    evidence = result.get_aggregated_evidence()
    assert "worker_a_hash" in evidence
    assert "worker_b_hash" in evidence
    assert "verifier_hash" in evidence


def test_cli_invocation(tmp_path):
    code = main([
        "--item", "P25_cli_test",
        "--key", "cli-test-secret",
        "--out-dir", str(tmp_path),
        "--mock-run",
    ])
    assert code == 0
    receipts = list(tmp_path.glob("*.json"))
    assert len(receipts) >= 1

    # Calling CLI without --mock-run must fail closed (returncode 2)
    code_no_mock = main([
        "--item", "P25_no_mock",
        "--key", "cli-test-secret",
        "--out-dir", str(tmp_path),
    ])
    assert code_no_mock == 2

    # Stage returning status="FAILED" dict must not be signed as valid stage output
    orchestrator = PipelineOrchestrator(secret_key="secret", out_dir=str(tmp_path))
    res_fail_dict = orchestrator.execute(
        item_id="task_fail_status_dict",
        worker_a_fn=lambda inp: {"status": "FAILED", "reason": "compile error"},
        worker_b_fn=lambda a: {"status": "PASS"},
        verifier_fn=lambda a, b: True,
    )
    assert res_fail_dict.status == "FAILED_STAGE_A"
    assert res_fail_dict.is_verified is False
    assert "worker_a" not in res_fail_dict.stage_receipts
