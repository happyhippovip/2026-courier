"""Tests for courier_core.quorum_verifier - Byzantine Fault Tolerant Consensus Quorum Verifier."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.quorum_verifier import (
    ByzantineQuorumVerifier,
    QuorumPolicy,
    WorkerProposal,
    DuplicateVoteError,
    InsufficientParticipantsError,
)


@pytest.fixture
def verifier() -> ByzantineQuorumVerifier:
    return ByzantineQuorumVerifier(min_participants=3, policy=QuorumPolicy.SUPERMAJORITY_TWO_THIRDS)


def test_unanimous_consensus(verifier: ByzantineQuorumVerifier):
    payload = {"status": "SUCCESS", "records_processed": 500}

    # 3 workers submit identical proposals
    for i in range(1, 4):
        verifier.submit_proposal(
            WorkerProposal(
                task_id="task-100",
                worker_id=f"worker-{i}",
                output_payload=payload,
            )
        )

    result = verifier.evaluate_quorum("task-100")
    assert result.achieved is True
    assert result.agreement_ratio == 1.0
    assert len(result.conforming_workers) == 3
    assert len(result.byzantine_workers) == 0
    assert result.consensus_output == payload


def test_byzantine_fault_isolated(verifier: ByzantineQuorumVerifier):
    correct_payload = {"calc": 42, "checksum": "abc"}
    rogue_payload = {"calc": 999, "checksum": "xyz"}  # Deviant

    # 3 honest workers
    for i in range(1, 4):
        verifier.submit_proposal(
            WorkerProposal(
                task_id="task-200",
                worker_id=f"worker-honest-{i}",
                output_payload=correct_payload,
            )
        )

    # 1 rogue worker
    verifier.submit_proposal(
        WorkerProposal(
            task_id="task-200",
            worker_id="worker-rogue-1",
            output_payload=rogue_payload,
        )
    )

    result = verifier.evaluate_quorum("task-200")
    assert result.achieved is True  # 3 out of 4 = 75% >= 66.7%
    assert result.consensus_output == correct_payload
    assert "worker-rogue-1" in result.byzantine_workers
    assert len(result.conforming_workers) == 3

    # Check reputation
    rep = verifier.get_worker_reputation("worker-rogue-1")
    assert rep["byzantine_count"] == 1
    assert rep["trust_score"] < 1.0


def test_split_brain_quorum_failure():
    verifier = ByzantineQuorumVerifier(min_participants=4, policy=QuorumPolicy.STRICT_MAJORITY)

    # 2 workers vote A, 2 workers vote B
    for i in range(1, 3):
        verifier.submit_proposal(
            WorkerProposal("task-split", worker_id=f"worker-a-{i}", output_payload={"result": "A"})
        )
    for i in range(1, 3):
        verifier.submit_proposal(
            WorkerProposal("task-split", worker_id=f"worker-b-{i}", output_payload={"result": "B"})
        )

    result = verifier.evaluate_quorum("task-split")
    assert result.achieved is False
    assert result.winning_digest is None
    assert result.consensus_output is None
    assert result.agreement_ratio == 0.5


def test_canonical_json_normalization(verifier: ByzantineQuorumVerifier):
    # Dicts with differently ordered keys
    p1 = {"alpha": 1, "beta": 2, "nested": {"y": 20, "x": 10}}
    p2 = {"nested": {"x": 10, "y": 20}, "beta": 2, "alpha": 1}

    verifier.submit_proposal(WorkerProposal("task-norm", "w1", p1))
    verifier.submit_proposal(WorkerProposal("task-norm", "w2", p2))
    verifier.submit_proposal(WorkerProposal("task-norm", "w3", p1))

    result = verifier.evaluate_quorum("task-norm")
    assert result.achieved is True
    assert result.agreement_ratio == 1.0
    assert len(result.conforming_workers) == 3


def test_sybil_defense_duplicate_worker_rejection(verifier: ByzantineQuorumVerifier):
    p = {"data": "sample"}
    verifier.submit_proposal(WorkerProposal("task-sybil", "worker-bad", p))

    # Same worker tries to vote again on the same task
    with pytest.raises(DuplicateVoteError):
        verifier.submit_proposal(WorkerProposal("task-sybil", "worker-bad", {"data": "other"}))


def test_worker_reputation_slashing(verifier: ByzantineQuorumVerifier):
    # Submit 3 rogue tasks for worker-slashed
    for task_idx in range(3):
        task_id = f"task-slash-{task_idx}"
        for i in range(1, 4):
            verifier.submit_proposal(WorkerProposal(task_id, f"honest-{i}", {"data": "honest"}))
        verifier.submit_proposal(WorkerProposal(task_id, "worker-slashed", {"data": "corrupt"}))
        verifier.evaluate_quorum(task_id)

    rep = verifier.get_worker_reputation("worker-slashed")
    assert rep["byzantine_count"] == 3
    assert rep["is_untrusted"] is True

    # Slashed worker cannot vote on future tasks
    from courier_core.quorum_verifier import QuorumError
    with pytest.raises(QuorumError, match="untrusted/slashed"):
        verifier.submit_proposal(WorkerProposal("task-future", "worker-slashed", {"data": "honest"}))

    # Forged result_digest is rejected on construction
    with pytest.raises(QuorumError, match="Forged result_digest"):
        WorkerProposal("task-forged", "w-honest", {"data": "real"}, result_digest="0" * 64)


def test_cli_quorum(capsys, monkeypatch):
    from courier_core.quorum_verifier import main

    # Submit 3 proposals
    for i in range(1, 4):
        monkeypatch.setattr(
            "sys.argv",
            [
                "quorum_verifier.py",
                "submit",
                "--task-id", "cli-t1",
                "--worker-id", f"w-{i}",
                "--payload", '{"val": 100}',
            ],
        )
        main()

    # Evaluate
    monkeypatch.setattr(
        "sys.argv",
        ["quorum_verifier.py", "evaluate", "--task-id", "cli-t1"],
    )
    main()
    out = capsys.readouterr().out
    assert "achieved: True" in out or '"achieved": true' in out.lower()
