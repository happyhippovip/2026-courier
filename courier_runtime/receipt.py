"""Recovery Receipt: what failed, what survived, what was done, where to resume.

validate() enforces the hard rules from the contract: only owned processes
may appear as retired, a non-idempotent task with an unconfirmed effect is
never resumed automatically, and RECOVERED needs evidence of progress after
detection.
"""
import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

ACTIONS = {"NONE", "RECONNECT_SURFACE", "RETIRE_OWNED_TREE", "RESUME_FROM_CHECKPOINT",
           "RETRY_AUTHORIZED_REQUIRED", "NEEDS_YOU"}
OUTCOMES = {"RECOVERED", "FAILED", "WAITING"}


class ReceiptError(ValueError):
    pass


@dataclass
class RecoveryReceipt:
    workkey: str
    session_id: str
    incident_fingerprint: str
    detected_state: str
    detected_at: float
    what_failed: str
    positive_evidence: Optional[str]
    survived: dict
    action: str
    outcome: str
    effect_class: Optional[str] = None
    effect_confirmed: bool = False
    retired: list = field(default_factory=list)
    before_snapshot: Optional[str] = None
    after_snapshot: Optional[str] = None
    progress_after_detection: bool = False
    resume_from: Optional[dict] = None
    evidence_refs: list = field(default_factory=list)
    receipt_id: str = field(default_factory=lambda: "rr-" + uuid.uuid4().hex)

    def to_json(self):
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, text):
        return cls(**json.loads(text))


def validate(receipt, owned_identities):
    """owned_identities: set of (pid, create_time) Courier recorded at spawn."""
    if receipt.action not in ACTIONS:
        raise ReceiptError(f"unknown action {receipt.action}")
    if receipt.outcome not in OUTCOMES:
        raise ReceiptError(f"unknown outcome {receipt.outcome}")
    for item in receipt.retired:
        if (item["pid"], item["create_time"]) not in owned_identities:
            raise ReceiptError(f"retired pid {item['pid']} was not owned")
    if receipt.action == "RESUME_FROM_CHECKPOINT":
        if receipt.effect_class not in ("idempotent", "non_idempotent"):
            raise ReceiptError("unknown effect class cannot authorize automatic resume")
        if receipt.effect_class == "non_idempotent" and receipt.effect_confirmed is not True:
            raise ReceiptError("non-idempotent work with an unconfirmed effect needs RETRY_AUTHORIZED, not resume")
    if receipt.action == "RESUME_FROM_CHECKPOINT" and not receipt.resume_from:
        raise ReceiptError("resume needs a resume_from checkpoint")
    if receipt.outcome == "RECOVERED" and not (receipt.after_snapshot and receipt.progress_after_detection):
        raise ReceiptError("RECOVERED needs an after-snapshot showing progress after detection")
    if receipt.what_failed in {"task", "worker_process"} and receipt.outcome == "FAILED" and not receipt.positive_evidence:
        raise ReceiptError("FAILED needs positive failure evidence")
    return receipt
