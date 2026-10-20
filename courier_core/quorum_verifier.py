"""Byzantine Fault Tolerant Consensus Quorum Verifier.

Aggregates worker output proposals, validates consensus thresholds (strict majority,
supermajority 2/3, unanimous), isolates Byzantine deviant workers, and manages
reputation scoring and rogue node slashing.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any


class QuorumPolicy(str, Enum):
    """Supported consensus policy thresholds."""

    STRICT_MAJORITY = "STRICT_MAJORITY"
    SUPERMAJORITY_TWO_THIRDS = "SUPERMAJORITY_TWO_THIRDS"
    UNANIMOUS = "UNANIMOUS"


class QuorumError(Exception):
    """Base exception for quorum verifier."""


class DuplicateVoteError(QuorumError):
    """Raised when a worker attempts to submit multiple conflicting votes for a task."""


class InsufficientParticipantsError(QuorumError):
    """Raised when evaluated task has fewer participants than the required minimum."""


def canonical_digest(payload: Any) -> str:
    """Produce deterministic SHA-256 digest of payload using canonical JSON serialization."""
    canonical_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


@dataclass
class WorkerProposal:
    """Proposal submitted by a worker for task verification."""

    task_id: str
    worker_id: str
    output_payload: dict[str, Any]
    result_digest: str | None = None
    timestamp: str | None = None

    def __post_init__(self) -> None:
        expected_digest = canonical_digest(self.output_payload)
        if self.result_digest is None:
            self.result_digest = expected_digest
        elif self.result_digest != expected_digest:
            raise QuorumError(
                f"Forged result_digest for worker {self.worker_id}: does not match canonical payload digest"
            )
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuorumResult:
    """Outcome of a quorum consensus evaluation."""

    task_id: str
    achieved: bool
    policy: QuorumPolicy
    winning_digest: str | None
    consensus_output: dict[str, Any] | None
    agreement_ratio: float
    participating_workers: list[str]
    conforming_workers: list[str]
    byzantine_workers: list[str]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["policy"] = self.policy.value
        return d


class ByzantineQuorumVerifier:
    """Consensus verifier detecting deviations and enforcing fault tolerance."""

    def __init__(
        self,
        min_participants: int = 3,
        policy: QuorumPolicy = QuorumPolicy.SUPERMAJORITY_TWO_THIRDS,
        slash_threshold: int = 3,
    ) -> None:
        self.min_participants = max(1, min_participants)
        self.policy = policy
        self.slash_threshold = max(1, slash_threshold)

        # task_id -> {worker_id -> WorkerProposal}
        self.proposals: dict[str, dict[str, WorkerProposal]] = {}
        # worker_id -> stats
        self.reputation: dict[str, dict[str, Any]] = {}

    def _ensure_reputation(self, worker_id: str) -> dict[str, Any]:
        if worker_id not in self.reputation:
            self.reputation[worker_id] = {
                "worker_id": worker_id,
                "total_votes": 0,
                "conforming_count": 0,
                "byzantine_count": 0,
                "trust_score": 1.0,
                "is_untrusted": False,
            }
        return self.reputation[worker_id]

    def submit_proposal(self, proposal: WorkerProposal) -> None:
        """Submit a worker proposal, guarding against Sybil duplicate votes and slashed workers."""
        rep = self.reputation.get(proposal.worker_id)
        if rep and rep.get("is_untrusted"):
            raise QuorumError(
                f"Worker {proposal.worker_id} is untrusted/slashed and cannot submit proposals"
            )
        task_id = proposal.task_id
        if task_id not in self.proposals:
            self.proposals[task_id] = {}

        if proposal.worker_id in self.proposals[task_id]:
            raise DuplicateVoteError(
                f"Worker {proposal.worker_id} has already voted for task {task_id}"
            )

        self.proposals[task_id][proposal.worker_id] = proposal

    def evaluate_quorum(self, task_id: str) -> QuorumResult:
        """Evaluate consensus for task proposals according to active policy."""
        proposals_map = self.proposals.get(task_id, {})
        proposals = list(proposals_map.values())

        if len(proposals) < self.min_participants:
            raise InsufficientParticipantsError(
                f"Task {task_id} has {len(proposals)} votes, minimum required is {self.min_participants}"
            )

        total_participants = len(proposals)
        all_workers = sorted([p.worker_id for p in proposals])

        # Group proposals by result_digest
        groups: dict[str, list[WorkerProposal]] = {}
        for p in proposals:
            assert p.result_digest is not None
            groups.setdefault(p.result_digest, []).append(p)

        # Find digest group with the highest vote count
        sorted_groups = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
        top_digest, top_proposals = sorted_groups[0]
        conforming_count = len(top_proposals)
        agreement_ratio = round(conforming_count / total_participants, 4)

        # Check policy requirement
        achieved = False
        if self.policy == QuorumPolicy.STRICT_MAJORITY:
            achieved = conforming_count > (total_participants / 2.0)
        elif self.policy == QuorumPolicy.SUPERMAJORITY_TWO_THIRDS:
            achieved = conforming_count >= (2.0 * total_participants / 3.0 - 1e-9)
        elif self.policy == QuorumPolicy.UNANIMOUS:
            achieved = conforming_count == total_participants

        if achieved:
            conforming_workers = sorted([p.worker_id for p in top_proposals])
            byzantine_workers = sorted(
                [p.worker_id for p in proposals if p.result_digest != top_digest]
            )
            consensus_output = top_proposals[0].output_payload

            # Update reputation
            for w in conforming_workers:
                rep = self._ensure_reputation(w)
                rep["total_votes"] += 1
                rep["conforming_count"] += 1
                rep["trust_score"] = round(rep["conforming_count"] / rep["total_votes"], 4)

            for w in byzantine_workers:
                rep = self._ensure_reputation(w)
                rep["total_votes"] += 1
                rep["byzantine_count"] += 1
                rep["trust_score"] = round(rep["conforming_count"] / rep["total_votes"], 4)
                if rep["byzantine_count"] >= self.slash_threshold:
                    rep["is_untrusted"] = True

            return QuorumResult(
                task_id=task_id,
                achieved=True,
                policy=self.policy,
                winning_digest=top_digest,
                consensus_output=consensus_output,
                agreement_ratio=agreement_ratio,
                participating_workers=all_workers,
                conforming_workers=conforming_workers,
                byzantine_workers=byzantine_workers,
            )
        else:
            return QuorumResult(
                task_id=task_id,
                achieved=False,
                policy=self.policy,
                winning_digest=None,
                consensus_output=None,
                agreement_ratio=agreement_ratio,
                participating_workers=all_workers,
                conforming_workers=[],
                byzantine_workers=[],
            )

    def get_worker_reputation(self, worker_id: str) -> dict[str, Any]:
        """Fetch reputation metrics for a worker."""
        return dict(self._ensure_reputation(worker_id))


_GLOBAL_VERIFIER: ByzantineQuorumVerifier | None = None


def get_global_verifier() -> ByzantineQuorumVerifier:
    global _GLOBAL_VERIFIER
    if _GLOBAL_VERIFIER is None:
        _GLOBAL_VERIFIER = ByzantineQuorumVerifier()
    return _GLOBAL_VERIFIER


def main() -> None:
    parser = argparse.ArgumentParser(description="Byzantine Fault Tolerant Quorum Verifier")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # submit
    sub_p = subparsers.add_parser("submit", help="Submit worker output proposal")
    sub_p.add_argument("--task-id", required=True, help="Task ID")
    sub_p.add_argument("--worker-id", required=True, help="Worker ID")
    sub_p.add_argument("--payload", required=True, help="JSON output payload")

    # evaluate
    eval_p = subparsers.add_parser("evaluate", help="Evaluate consensus quorum")
    eval_p.add_argument("--task-id", required=True, help="Task ID")

    # reputation
    rep_p = subparsers.add_parser("reputation", help="Check worker reputation")
    rep_p.add_argument("--worker-id", required=True, help="Worker ID")

    args = parser.parse_args()
    verifier = get_global_verifier()

    if args.action == "submit":
        payload = json.loads(args.payload)
        proposal = WorkerProposal(task_id=args.task_id, worker_id=args.worker_id, output_payload=payload)
        verifier.submit_proposal(proposal)
        print(f"Submitted proposal for {args.task_id} from {args.worker_id}")
    elif args.action == "evaluate":
        result = verifier.evaluate_quorum(args.task_id)
        print(json.dumps(result.to_dict(), indent=2))
    elif args.action == "reputation":
        rep = verifier.get_worker_reputation(args.worker_id)
        print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
