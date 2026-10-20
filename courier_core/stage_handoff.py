"""Multi-Stage Worker Chain & Cryptographic Witness Orchestrator.

Orchestrates sequential worker chains:
DISPATCH -> WORKER_A -> HANDOFF -> WORKER_B -> VERIFIER -> DONE
with cryptographic HMAC-SHA256 stage witness tokens and chained hash integrity.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import datetime
from enum import Enum
import hashlib
import hmac
import json
from pathlib import Path
import sys
from typing import Any, Optional


class StageType(str, Enum):
    DISPATCH = "DISPATCH"
    WORKER_A = "WORKER_A"
    HANDOFF = "HANDOFF"
    WORKER_B = "WORKER_B"
    VERIFIER = "VERIFIER"
    DONE = "DONE"


ORDERED_STAGES = [
    StageType.DISPATCH,
    StageType.WORKER_A,
    StageType.HANDOFF,
    StageType.WORKER_B,
    StageType.VERIFIER,
    StageType.DONE,
]


class StageHandoffError(Exception):
    """Base exception for stage handoff orchestration."""


class TamperedWitnessChainError(StageHandoffError):
    """Raised when a stage token signature or digest fails verification."""


class BrokenWitnessChainError(StageHandoffError):
    """Raised when prev_token_hash does not match the previous token digest."""


class PipelineAbortedError(StageHandoffError):
    """Raised when advancing an aborted pipeline."""


class PipelineAlreadyCompletedError(StageHandoffError):
    """Raised when attempting to advance a pipeline that has already reached DONE."""


@dataclass(frozen=True)
class StageWitnessToken:
    """Cryptographic attestation token generated upon completion of a pipeline stage."""

    stage_id: str
    stage_type: StageType
    worker_id: str
    output_hash: str
    timestamp: str
    prev_token_hash: Optional[str]
    signature: str

    def canonical_bytes(self) -> bytes:
        payload = {
            "stage_id": self.stage_id,
            "stage_type": self.stage_type.value if isinstance(self.stage_type, StageType) else str(self.stage_type),
            "worker_id": self.worker_id,
            "output_hash": self.output_hash,
            "timestamp": self.timestamp,
            "prev_token_hash": self.prev_token_hash,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return canonical_json.encode("utf-8")

    @property
    def token_hash(self) -> str:
        payload = self.to_dict()
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "stage_type": self.stage_type.value if isinstance(self.stage_type, StageType) else str(self.stage_type),
            "worker_id": self.worker_id,
            "output_hash": self.output_hash,
            "timestamp": self.timestamp,
            "prev_token_hash": self.prev_token_hash,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageWitnessToken:
        return cls(
            stage_id=str(data["stage_id"]),
            stage_type=StageType(data["stage_type"]),
            worker_id=str(data["worker_id"]),
            output_hash=str(data["output_hash"]),
            timestamp=str(data["timestamp"]),
            prev_token_hash=data.get("prev_token_hash"),
            signature=str(data["signature"]),
        )


class StageHandoffPipeline:
    """Sequential pipeline managing stages and cryptographic witness chain."""

    def __init__(
        self,
        pipeline_id: str,
        secret_key: str,
        current_stage_index: int = 0,
        witness_chain: Optional[list[StageWitnessToken]] = None,
        is_aborted: bool = False,
        abort_reason: Optional[str] = None,
    ) -> None:
        self.pipeline_id = pipeline_id
        self.secret_key = secret_key
        self.current_stage_index = current_stage_index
        self.witness_chain: list[StageWitnessToken] = witness_chain or []
        self.is_aborted = is_aborted
        self.abort_reason = abort_reason

    @classmethod
    def create(cls, pipeline_id: str, secret_key: str) -> StageHandoffPipeline:
        return cls(pipeline_id=pipeline_id, secret_key=secret_key)

    @property
    def current_stage(self) -> Optional[StageType]:
        if self.current_stage_index < len(ORDERED_STAGES):
            return ORDERED_STAGES[self.current_stage_index]
        return None

    @property
    def is_completed(self) -> bool:
        return (
            not self.is_aborted
            and len(self.witness_chain) == len(ORDERED_STAGES)
            and self.current_stage_index >= len(ORDERED_STAGES)
        )

    def advance(self, worker_id: str, output_data: bytes) -> StageWitnessToken:
        """Advance to next pipeline stage and append HMAC-signed witness token."""
        if self.is_aborted:
            raise PipelineAbortedError(f"Pipeline has been aborted: {self.abort_reason}")

        if self.is_completed:
            raise PipelineAlreadyCompletedError("Pipeline has already reached DONE")

        current_stage_type = ORDERED_STAGES[self.current_stage_index]
        stage_id = f"{self.pipeline_id}-{current_stage_type.value.lower()}"
        output_hash = hashlib.sha256(output_data).hexdigest()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        prev_token_hash = self.witness_chain[-1].token_hash if self.witness_chain else None

        # Build unsigned payload for signature
        temp_token = StageWitnessToken(
            stage_id=stage_id,
            stage_type=current_stage_type,
            worker_id=worker_id,
            output_hash=output_hash,
            timestamp=now_iso,
            prev_token_hash=prev_token_hash,
            signature="",
        )
        sig = hmac.new(
            self.secret_key.encode("utf-8"),
            temp_token.canonical_bytes(),
            hashlib.sha256,
        ).hexdigest()

        token = StageWitnessToken(
            stage_id=stage_id,
            stage_type=current_stage_type,
            worker_id=worker_id,
            output_hash=output_hash,
            timestamp=now_iso,
            prev_token_hash=prev_token_hash,
            signature=sig,
        )

        self.witness_chain.append(token)
        self.current_stage_index += 1
        return token

    def fail(self, worker_id: str, reason: str) -> None:
        """Mark pipeline as aborted with fail-closed reason."""
        self.is_aborted = True
        self.abort_reason = reason

    def verify_chain(self) -> bool:
        """Verify unbroken cryptographic integrity of entire witness token sequence."""
        if self.is_aborted:
            raise PipelineAbortedError(f"Pipeline has been aborted: {self.abort_reason}")
        if not self.witness_chain:
            raise BrokenWitnessChainError("Cannot verify empty witness chain")

        prev_hash: Optional[str] = None

        for idx, token in enumerate(self.witness_chain):
            # Verify stage ordering
            expected_stage = ORDERED_STAGES[idx]
            if token.stage_type != expected_stage:
                raise BrokenWitnessChainError(
                    f"Out of order stage at index {idx}: expected {expected_stage}, got {token.stage_type}"
                )

            # Verify link to previous token
            if token.prev_token_hash != prev_hash:
                raise BrokenWitnessChainError(
                    f"Broken chain link at index {idx}: expected prev {prev_hash}, got {token.prev_token_hash}"
                )

            # Verify signature
            expected_sig = hmac.new(
                self.secret_key.encode("utf-8"),
                token.canonical_bytes(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(token.signature, expected_sig):
                raise TamperedWitnessChainError(
                    f"Invalid witness token signature at stage {token.stage_type}"
                )

            prev_hash = token.token_hash

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "current_stage_index": self.current_stage_index,
            "is_aborted": self.is_aborted,
            "abort_reason": self.abort_reason,
            "witness_chain": [t.to_dict() for t in self.witness_chain],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], secret_key: str) -> StageHandoffPipeline:
        chain = [StageWitnessToken.from_dict(t) for t in data.get("witness_chain", [])]
        return cls(
            pipeline_id=str(data["pipeline_id"]),
            secret_key=secret_key,
            current_stage_index=int(data.get("current_stage_index", 0)),
            witness_chain=chain,
            is_aborted=bool(data.get("is_aborted", False)),
            abort_reason=data.get("abort_reason"),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Stage Worker Chain & Witness Orchestrator")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # init
    init_p = subparsers.add_parser("init", help="Initialize pipeline state")
    init_p.add_argument("--pipeline-id", required=True, help="Pipeline identifier")
    init_p.add_argument("--secret", required=True, help="Cryptographic signing secret")
    init_p.add_argument("--output", required=True, help="Output state JSON file")

    # advance
    adv_p = subparsers.add_parser("advance", help="Advance pipeline to next stage")
    adv_p.add_argument("--file", required=True, help="Pipeline state JSON file")
    adv_p.add_argument("--worker", required=True, help="Worker identifier executing stage")
    adv_p.add_argument("--data", required=True, help="Stage output payload data string")
    adv_p.add_argument("--secret", required=True, help="Cryptographic signing secret")

    # verify
    ver_p = subparsers.add_parser("verify", help="Verify witness chain integrity")
    ver_p.add_argument("--file", required=True, help="Pipeline state JSON file")
    ver_p.add_argument("--secret", required=True, help="Cryptographic signing secret")

    args = parser.parse_args()

    if args.action == "init":
        pipeline = StageHandoffPipeline.create(pipeline_id=args.pipeline_id, secret_key=args.secret)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(pipeline.to_dict(), f, indent=2)
        print(f"Initialized pipeline {args.pipeline_id} at {args.output}")

    elif args.action == "advance":
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        pipeline = StageHandoffPipeline.from_dict(data, secret_key=args.secret)
        tok = pipeline.advance(worker_id=args.worker, output_data=args.data.encode("utf-8"))
        with open(args.file, "w", encoding="utf-8") as f:
            json.dump(pipeline.to_dict(), f, indent=2)
        print(f"Advanced stage {tok.stage_type} (hash={tok.token_hash[:8]})")

    elif args.action == "verify":
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        pipeline = StageHandoffPipeline.from_dict(data, secret_key=args.secret)
        try:
            pipeline.verify_chain()
            print("CHAIN_VERIFIED_OK")
        except StageHandoffError as e:
            print(f"CHAIN_VERIFICATION_FAILED: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
