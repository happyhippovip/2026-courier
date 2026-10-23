from pathlib import Path

from scripts.agent_handoff import (
    AgentHandoffReceipt, HostOS, AuthorityLevel, HandoffStatus,
    ContinuationGate, EvidenceItem, HandoffValidator
)
from datetime import datetime, timezone
import hashlib

def test_agent_handoff_receipt_validation():
    validator = HandoffValidator()
    receipt = AgentHandoffReceipt(
        origin="mac_google_antigravity",
        agent_instance="ag-1234",
        assignment_id="task-5678",
        host_os=HostOS.MACOS,
        authority=AuthorityLevel.MUTABLE_L2,
        created_at=datetime.now(timezone.utc).isoformat(),
        status=HandoffStatus.CHANGED,
        new_findings=["Found issue in schema"],
        changed_findings=[],
        resolved_findings=["Fixed schema validation"],
        blocking_findings=[],
        evidence=[
            EvidenceItem(path="tests/test_agent_handoff.py", hash="abc123hash", type="test_file", command="pytest")
        ],
        actions_taken=["Created handoff schema and python bindings"],
        production_files_modified=["courier_core/schemas/agent_handoff_receipt.schema.json", "scripts/agent_handoff.py"],
        waiting_for=[],
        safe_parallel_work=["L6 Windows packaging"],
        next_independent_task="Implement Chief Ingestion",
        recommended_next_agent="chief_coordinator",
        continuation_gate=ContinuationGate.OPEN,
        wait_resume_contract="resume immediately",
        previous_receipt_hash=None,
        receipt_hash=hashlib.sha256(b"receipt").hexdigest()
    )
    validator.validate(receipt)


def _receipt():
    return AgentHandoffReceipt(
        origin="mac_google_antigravity",
        agent_instance="ag-1234",
        assignment_id="task-5678",
        host_os=HostOS.MACOS,
        authority=AuthorityLevel.MUTABLE_L2,
        created_at=datetime.now(timezone.utc).isoformat(),
        status=HandoffStatus.CHANGED,
        new_findings=["Found issue in schema"],
        changed_findings=[],
        resolved_findings=["Fixed schema validation"],
        blocking_findings=[],
        evidence=[
            EvidenceItem(path="tests/test_agent_handoff.py", hash="abc123hash", type="test_file", command="pytest")
        ],
        actions_taken=["Created handoff schema and python bindings"],
        production_files_modified=["scripts/agent_handoff.py"],
        waiting_for=[],
        safe_parallel_work=["L6 Windows packaging"],
        next_independent_task="Implement Chief Ingestion",
        recommended_next_agent="chief_coordinator",
        continuation_gate=ContinuationGate.OPEN,
        wait_resume_contract="resume immediately",
        previous_receipt_hash=None,
        receipt_hash=hashlib.sha256(b"receipt").hexdigest(),
    )


def test_schema_file_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside-schema.json"
    outside.write_text("true\n", encoding="utf-8")
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "agent_handoff_receipt.schema.json").symlink_to(outside)

    def run(schemas):
        try:
            HandoffValidator(str(schemas)).validate(_receipt())
            return None
        except ValueError as exc:
            return str(exc)

    file_err = run(schema_dir)
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "agent_handoff_receipt.schema.json").write_text("true\n", encoding="utf-8")
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-schemas"
    linked.symlink_to(parent_outside)
    parent_err = run(linked)
    names = sorted(path.name for path in parent_outside.iterdir())
    assert (file_err, parent_err, outside.read_text(encoding="utf-8"), names) == (
        "refusing to follow a symlink",
        "refusing to follow a symlink",
        "true\n",
        ["agent_handoff_receipt.schema.json", "keep.txt"],
    )
