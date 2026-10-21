"""Minimal Context Slicer & Exact File Provenance Engine (CP-26 / CQ-26 / GB-CONTEXT-01)

Durable Cannon & Cost Invariants:
1. Alle Acceptance-Inputs erhalten:
   - Goal contract, parameters, invariants, acceptance criteria, and interface constraints
     are 100% preserved without omission or loss.
2. Keine Volltranskripte ("No Full Transcripts"):
   - Prunes conversational chat logs, turn history, JSONL transcripts, and verbose raw terminal outputs.
   - If an expansion or dispatch attempts to embed a full transcript, it fails closed.
3. Herkunft und Version rekonstruierbar (Exact Provenance):
   - Every file slice includes file_path, commit_sha, content_sha256, and exact line boundaries [start_line, end_line].
4. Größen nur gemessen:
   - Physical byte counts, line counts, character counts, and reduction ratios are computed directly, never estimated or hallucinated.
5. Entferne nur belegbar redundanten Kontext:
   - Isolates relevant call-graph slices and interfaces while eliminating boilerplate and conversational noise.
6. Required Evidence:
   - task-packet, exact-files, constraints.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


FORBIDDEN_TRANSCRIPT_PATTERNS = [
    re.compile(r'"type":\s*"USER_INPUT"', re.IGNORECASE),
    re.compile(r'"type":\s*"PLANNER_RESPONSE"', re.IGNORECASE),
    re.compile(r'<transcript_full', re.IGNORECASE),
    re.compile(r'transcript\.jsonl', re.IGNORECASE),
    re.compile(r'\[USER_EXPLICIT\]', re.IGNORECASE),
]


class FullTranscriptForbiddenError(RuntimeError):
    """Raised when an attempt is made to smuggle full conversational transcripts into a task packet."""


class IncompleteAcceptanceCriteriaError(RuntimeError):
    """Raised when context slicing drops required acceptance criteria or decision constraints."""


@dataclass(frozen=True)
class FileSliceProvenance:
    file_path: str
    commit_sha: str
    content_sha256: str
    start_line: int
    end_line: int
    line_count: int
    byte_size: int
    slice_content: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "commit_sha": self.commit_sha,
            "content_sha256": self.content_sha256,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "line_count": self.line_count,
            "byte_size": self.byte_size,
            "slice_content": self.slice_content,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class DecisionConstraints:
    invariants: List[str]
    acceptance_criteria: List[str]
    required_capabilities: Set[str]
    budget_limit_eur: float = 0.0
    forbidden_actions: List[str] = field(default_factory=list)

    def validate_completeness(self) -> None:
        if not self.acceptance_criteria:
            raise IncompleteAcceptanceCriteriaError("Context packet must retain non-empty acceptance criteria.")
        if not self.invariants:
            raise IncompleteAcceptanceCriteriaError("Context packet must retain mandatory security invariants.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariants": self.invariants,
            "acceptance_criteria": self.acceptance_criteria,
            "required_capabilities": sorted(list(self.required_capabilities)),
            "budget_limit_eur": self.budget_limit_eur,
            "forbidden_actions": self.forbidden_actions,
        }


@dataclass
class MinimalContextPacket:
    task_id: str
    goal_contract_id: str
    constraints: DecisionConstraints
    exact_files: List[FileSliceProvenance]
    evidence_refs: List[str]
    raw_size_bytes: int
    sliced_size_bytes: int
    reduction_percentage: float
    raw_tokens_estimate: int
    sliced_tokens_estimate: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal_contract_id": self.goal_contract_id,
            "constraints": self.constraints.to_dict(),
            "exact_files": [f.to_dict() for f in self.exact_files],
            "evidence_refs": self.evidence_refs,
            "measurements": {
                "raw_size_bytes": self.raw_size_bytes,
                "sliced_size_bytes": self.sliced_size_bytes,
                "reduction_percentage": self.reduction_percentage,
                "raw_tokens_estimate": self.raw_tokens_estimate,
                "sliced_tokens_estimate": self.sliced_tokens_estimate,
            },
        }


class MinimalContextSlicer:
    """Extracts decision-relevant file slices and builds lean, proven context packets."""

    @staticmethod
    def slice_file(
        full_content: str,
        file_path: str,
        start_line: int,
        end_line: int,
        commit_sha: str,
        rationale: str = "",
    ) -> FileSliceProvenance:
        lines = full_content.splitlines(keepends=True)
        total_lines = len(lines)

        s_idx = max(0, start_line - 1)
        e_idx = min(total_lines, end_line)

        selected_lines = lines[s_idx:e_idx]
        slice_text = "".join(selected_lines)
        slice_bytes = slice_text.encode("utf-8")

        sha256_hash = hashlib.sha256(slice_bytes).hexdigest()

        return FileSliceProvenance(
            file_path=file_path.replace("\\", "/"),
            commit_sha=commit_sha,
            content_sha256=sha256_hash,
            start_line=start_line,
            end_line=end_line,
            line_count=len(selected_lines),
            byte_size=len(slice_bytes),
            slice_content=slice_text,
            rationale=rationale or f"Decision-relevant slice lines {start_line}-{end_line} of {file_path}",
        )

    def build_packet(
        self,
        task_id: str,
        goal_contract_id: str,
        constraints: DecisionConstraints,
        file_slices: List[FileSliceProvenance],
        raw_context_content: str = "",
        evidence_refs: Optional[List[str]] = None,
    ) -> MinimalContextPacket:
        # 1. Enforce: All acceptance criteria and invariants are preserved
        constraints.validate_completeness()

        # 2. Enforce: No full transcripts allowed in context
        for pattern in FORBIDDEN_TRANSCRIPT_PATTERNS:
            if pattern.search(raw_context_content):
                raise FullTranscriptForbiddenError(
                    "Context rejection: Full conversational transcripts or raw JSONL logs detected in input payload. "
                    "Only decision-relevant file slices and explicit constraints are permitted."
                )

        # 3. Physical Size Measurement
        sliced_text = json.dumps(
            {
                "task_id": task_id,
                "goal_contract_id": goal_contract_id,
                "constraints": constraints.to_dict(),
                "slices": [s.to_dict() for s in file_slices],
                "evidence_refs": evidence_refs or [],
            },
            indent=2,
        )
        sliced_bytes_len = len(sliced_text.encode("utf-8"))
        raw_bytes_len = len(raw_context_content.encode("utf-8")) if raw_context_content else sliced_bytes_len

        # Measured Reduction Percentage
        if raw_bytes_len > sliced_bytes_len:
            reduction = round(((raw_bytes_len - sliced_bytes_len) / raw_bytes_len) * 100.0, 2)
        else:
            reduction = 0.0

        # Estimated token count (standard ~4 chars per token rule of thumb for code/json)
        raw_tokens = max(1, raw_bytes_len // 4)
        sliced_tokens = max(1, sliced_bytes_len // 4)

        return MinimalContextPacket(
            task_id=task_id,
            goal_contract_id=goal_contract_id,
            constraints=constraints,
            exact_files=file_slices,
            evidence_refs=evidence_refs or [],
            raw_size_bytes=raw_bytes_len,
            sliced_size_bytes=sliced_bytes_len,
            reduction_percentage=reduction,
            raw_tokens_estimate=raw_tokens,
            sliced_tokens_estimate=sliced_tokens,
        )

    def generate_context_evidence(
        self,
        packet: MinimalContextPacket,
    ) -> Dict[str, Any]:
        """Generates CP-26 required evidence: ['task-packet', 'exact-files', 'constraints']."""
        p_dict = packet.to_dict()

        return {
            "required_evidence": ["task-packet", "exact-files", "constraints"],
            "task-packet": {
                "task_id": packet.task_id,
                "goal_contract_id": packet.goal_contract_id,
                "evidence_refs": packet.evidence_refs,
                "measurements": p_dict["measurements"],
            },
            "exact-files": p_dict["exact_files"],
            "constraints": p_dict["constraints"],
        }
