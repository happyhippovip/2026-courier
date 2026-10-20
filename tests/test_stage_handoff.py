"""Tests for courier_core.stage_handoff - Multi-Stage Worker Chain & Cryptographic Witness Orchestrator."""

from __future__ import annotations

import json
import pytest

from courier_core.stage_handoff import (
    StageType,
    StageWitnessToken,
    StageHandoffPipeline,
    TamperedWitnessChainError,
    BrokenWitnessChainError,
    PipelineAbortedError,
    PipelineAlreadyCompletedError,
    main,
)


def test_pipeline_creation_and_full_chain_traversal():
    secret = "courier-stage-secret-2026"
    pipeline = StageHandoffPipeline.create(pipeline_id="pipe-real-chain-01", secret_key=secret)

    assert pipeline.current_stage == StageType.DISPATCH
    assert not pipeline.is_completed
    assert len(pipeline.witness_chain) == 0

    # Advance DISPATCH
    tok1 = pipeline.advance(worker_id="dispatcher-win", output_data=b"dispatch: spec 101")
    assert tok1.stage_type == StageType.DISPATCH
    assert tok1.prev_token_hash is None
    assert pipeline.current_stage == StageType.WORKER_A

    # Advance WORKER_A
    tok2 = pipeline.advance(worker_id="worker-a-win", output_data=b"worker_a: build compiled")
    assert tok2.stage_type == StageType.WORKER_A
    assert tok2.prev_token_hash == tok1.token_hash
    assert pipeline.current_stage == StageType.HANDOFF

    # Advance HANDOFF
    tok3 = pipeline.advance(worker_id="coordinator", output_data=b"handoff: artifact routed")
    assert tok3.stage_type == StageType.HANDOFF
    assert tok3.prev_token_hash == tok2.token_hash
    assert pipeline.current_stage == StageType.WORKER_B

    # Advance WORKER_B
    tok4 = pipeline.advance(worker_id="worker-b-win", output_data=b"worker_b: integration test passed")
    assert tok4.stage_type == StageType.WORKER_B
    assert tok4.prev_token_hash == tok3.token_hash
    assert pipeline.current_stage == StageType.VERIFIER

    # Advance VERIFIER
    tok5 = pipeline.advance(worker_id="verifier-independent", output_data=b"verifier: cryptographic pass")
    assert tok5.stage_type == StageType.VERIFIER
    assert tok5.prev_token_hash == tok4.token_hash
    assert pipeline.current_stage == StageType.DONE

    # Advance DONE
    tok6 = pipeline.advance(worker_id="ledger-finalizer", output_data=b"done: release certified")
    assert tok6.stage_type == StageType.DONE
    assert tok6.prev_token_hash == tok5.token_hash
    assert pipeline.is_completed

    # Verify unbroken chain
    assert pipeline.verify_chain() is True

    # Advance after completion raises
    with pytest.raises(PipelineAlreadyCompletedError):
        pipeline.advance(worker_id="extra", output_data=b"extra")


def test_tampered_token_signature_detection():
    secret = "secret-key-1"
    pipeline = StageHandoffPipeline.create(pipeline_id="pipe-tamper-1", secret_key=secret)
    pipeline.advance(worker_id="dispatcher", output_data=b"seed data")
    pipeline.advance(worker_id="worker-a", output_data=b"stage 1 data")

    # Serialize and tamper with signature
    raw = pipeline.to_dict()
    raw["witness_chain"][1]["signature"] = "0" * 64

    tampered_pipeline = StageHandoffPipeline.from_dict(raw, secret_key=secret)
    with pytest.raises(TamperedWitnessChainError, match="Invalid witness token signature"):
        tampered_pipeline.verify_chain()


def test_broken_chain_linkage_detection():
    secret = "secret-key-2"
    pipeline = StageHandoffPipeline.create(pipeline_id="pipe-broken-link", secret_key=secret)
    pipeline.advance(worker_id="dispatcher", output_data=b"seed data")
    pipeline.advance(worker_id="worker-a", output_data=b"stage 1 data")

    # Corrupt prev_token_hash link
    raw = pipeline.to_dict()
    raw["witness_chain"][1]["prev_token_hash"] = "f" * 64

    corrupted_pipeline = StageHandoffPipeline.from_dict(raw, secret_key=secret)
    with pytest.raises(BrokenWitnessChainError, match="Broken chain link"):
        corrupted_pipeline.verify_chain()


def test_pipeline_fail_closed_abortion():
    secret = "secret-key-3"
    pipeline = StageHandoffPipeline.create(pipeline_id="pipe-fail", secret_key=secret)
    pipeline.advance(worker_id="dispatcher", output_data=b"task dispatched")

    # Worker A fails
    pipeline.fail(worker_id="worker-a", reason="Memory limit exceeded in sandbox")
    assert pipeline.is_aborted
    assert pipeline.abort_reason == "Memory limit exceeded in sandbox"

    # Subsequent advance or verify_chain must fail closed
    with pytest.raises(PipelineAbortedError, match="Pipeline has been aborted"):
        pipeline.advance(worker_id="worker-b", output_data=b"ignored")
    with pytest.raises(PipelineAbortedError, match="Pipeline has been aborted"):
        pipeline.verify_chain()


def test_empty_witness_chain_rejected():
    pipeline = StageHandoffPipeline.create(pipeline_id="pipe-empty", secret_key="secret")
    with pytest.raises(BrokenWitnessChainError, match="empty witness chain"):
        pipeline.verify_chain()


def test_wrong_secret_key_verification():
    secret = "correct-secret"
    pipeline = StageHandoffPipeline.create(pipeline_id="pipe-wrong-key", secret_key=secret)
    pipeline.advance(worker_id="dispatcher", output_data=b"data")

    raw = pipeline.to_dict()
    pipeline_bad_key = StageHandoffPipeline.from_dict(raw, secret_key="wrong-secret")
    with pytest.raises(TamperedWitnessChainError):
        pipeline_bad_key.verify_chain()


def test_cli_stage_handoff_workflow(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "pipeline.json"
    secret = "cli-test-secret-42"

    # Init
    monkeypatch.setattr(
        "sys.argv",
        ["stage_handoff.py", "init", "--pipeline-id", "cli-pipe-01", "--secret", secret, "--output", str(state_file)],
    )
    main()
    assert state_file.exists()

    # Advance DISPATCH
    monkeypatch.setattr(
        "sys.argv",
        ["stage_handoff.py", "advance", "--file", str(state_file), "--worker", "dispatcher", "--data", "spec 1", "--secret", secret],
    )
    main()

    # Verify
    monkeypatch.setattr(
        "sys.argv",
        ["stage_handoff.py", "verify", "--file", str(state_file), "--secret", secret],
    )
    main()
    out = capsys.readouterr().out
    assert "CHAIN_VERIFIED_OK" in out
