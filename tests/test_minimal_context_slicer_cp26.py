"""Tests for CP-26 / CQ-26 / GB-CONTEXT-01: Minimal Context Slicer & Exact File Provenance

Verifies:
1. All acceptance inputs, goals, and security invariants are 100% preserved.
2. Full conversational transcripts and raw chat logs are strictly forbidden.
3. Exact file slice provenance (path, commit SHA, line boundaries, content hash) is reconstructible.
4. Sizes are physically measured with verifiable token/byte reduction.
5. Evidence generated with ['task-packet', 'exact-files', 'constraints'].
"""

import pytest

from courier_core.minimal_context_slicer import (
    DecisionConstraints,
    FileSliceProvenance,
    FullTranscriptForbiddenError,
    IncompleteAcceptanceCriteriaError,
    MinimalContextSlicer,
)


def test_all_acceptance_inputs_and_constraints_preserved():
    slicer = MinimalContextSlicer()

    # Case A: Valid constraints
    constraints = DecisionConstraints(
        invariants=["SINGLE_WRITER=YES", "AUTONOMOUS_SPEND_LIMIT_EUR=0.00", "PAYG=FORBIDDEN"],
        acceptance_criteria=[
            "All unit test assertions must pass without regressions.",
            "Execution must produce zero external side effects in dry-run mode.",
        ],
        required_capabilities={"python", "git"},
        budget_limit_eur=0.0,
        forbidden_actions=["publish_to_pypi", "auto_merge_main"],
    )

    slice_record = slicer.slice_file(
        full_content="def target():\n    return 42\n",
        file_path="src/service.py",
        start_line=1,
        end_line=2,
        commit_sha="commit-abc1234",
    )

    packet = slicer.build_packet(
        task_id="task-slice-01",
        goal_contract_id="goal-42",
        constraints=constraints,
        file_slices=[slice_record],
    )

    assert packet.task_id == "task-slice-01"
    assert packet.constraints.acceptance_criteria == constraints.acceptance_criteria
    assert packet.constraints.invariants == constraints.invariants
    assert packet.constraints.required_capabilities == {"python", "git"}

    # Case B: Incomplete criteria fails closed
    with pytest.raises(IncompleteAcceptanceCriteriaError, match="non-empty acceptance criteria"):
        DecisionConstraints(
            invariants=["SINGLE_WRITER=YES"],
            acceptance_criteria=[],
            required_capabilities={"python"},
        ).validate_completeness()


def test_full_transcripts_are_strictly_forbidden():
    slicer = MinimalContextSlicer()
    constraints = DecisionConstraints(
        invariants=["SINGLE_WRITER=YES"],
        acceptance_criteria=["Must reject bloated conversational transcripts."],
        required_capabilities={"python"},
    )

    slice_record = slicer.slice_file(
        full_content="def run(): pass\n",
        file_path="src/main.py",
        start_line=1,
        end_line=1,
        commit_sha="c1",
    )

    # Raw context containing conversational JSONL transcript turns
    bloated_transcript = '{"step_index": 1, "type": "USER_INPUT", "content": "Hello bot please write code"}'

    with pytest.raises(FullTranscriptForbiddenError, match="Full conversational transcripts or raw JSONL logs detected"):
        slicer.build_packet(
            task_id="task-err",
            goal_contract_id="goal-err",
            constraints=constraints,
            file_slices=[slice_record],
            raw_context_content=bloated_transcript,
        )


def test_exact_file_slice_provenance_and_hash():
    slicer = MinimalContextSlicer()

    code = """# Header comment line 1
# Header comment line 2
class TargetService:
    def execute(self):
        return "success"
# Trailing line 7
# Trailing line 8
"""

    slice_record = slicer.slice_file(
        full_content=code,
        file_path="services/worker.py",
        start_line=3,
        end_line=5,
        commit_sha="sha-fedcba9876",
        rationale="Target service class and execute method contract",
    )

    assert slice_record.file_path == "services/worker.py"
    assert slice_record.commit_sha == "sha-fedcba9876"
    assert slice_record.start_line == 3
    assert slice_record.end_line == 5
    assert slice_record.line_count == 3
    assert "class TargetService:" in slice_record.slice_content
    assert "return \"success\"" in slice_record.slice_content
    assert len(slice_record.content_sha256) == 64  # Valid SHA-256


def test_sizes_are_physically_measured_with_proven_reduction():
    slicer = MinimalContextSlicer()

    # Generate a bulky raw context (10,000 characters of repetitive boilerplate)
    bulky_raw_context = ("# Large redundant code file\n" + "x = 1\n" * 1500)

    # Lean targeted slice
    slice_record = slicer.slice_file(
        full_content=bulky_raw_context,
        file_path="src/big_file.py",
        start_line=5,
        end_line=10,
        commit_sha="sha-clean",
    )

    constraints = DecisionConstraints(
        invariants=["SINGLE_WRITER=YES"],
        acceptance_criteria=["Verify size reduction is physically measured."],
        required_capabilities={"python"},
    )

    packet = slicer.build_packet(
        task_id="task-reduction-test",
        goal_contract_id="goal-reduction",
        constraints=constraints,
        file_slices=[slice_record],
        raw_context_content=bulky_raw_context,
    )

    assert packet.raw_size_bytes == len(bulky_raw_context.encode("utf-8"))
    assert packet.sliced_size_bytes < packet.raw_size_bytes
    assert packet.reduction_percentage > 80.0  # Demonstrates >80% context compaction
    assert packet.raw_tokens_estimate > packet.sliced_tokens_estimate


def test_evidence_generation():
    slicer = MinimalContextSlicer()
    constraints = DecisionConstraints(
        invariants=["SINGLE_WRITER=YES"],
        acceptance_criteria=["Must generate evidence dictionary."],
        required_capabilities={"python"},
    )

    slice_record = slicer.slice_file(
        full_content="def test(): pass\n",
        file_path="tests/t.py",
        start_line=1,
        end_line=1,
        commit_sha="c1",
    )

    packet = slicer.build_packet(
        task_id="t1",
        goal_contract_id="g1",
        constraints=constraints,
        file_slices=[slice_record],
        evidence_refs=["ref-01"],
    )

    evidence = slicer.generate_context_evidence(packet)

    assert evidence["required_evidence"] == ["task-packet", "exact-files", "constraints"]
    assert evidence["task-packet"]["task_id"] == "t1"
    assert len(evidence["exact-files"]) == 1
    assert "SINGLE_WRITER=YES" in evidence["constraints"]["invariants"]
