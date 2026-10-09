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
