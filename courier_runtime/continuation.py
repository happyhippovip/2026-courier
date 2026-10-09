"""Verified continuation: resume from what was accepted, not from rereading logs.

AcceptedLog is append-only accepted state with provenance (raw evidence and
logs are never promoted by themselves). A Checkpoint names the last accepted
step and what was only attempted. decide() answers, after an interruption:
what was I doing, what was accepted, what was only attempted, which owned
processes still exist, which authority is still valid, and whether it is
safe to continue - and from where.
"""
import json
import os
import time
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class AcceptedFact:
    workkey: str
    step: int
    statement: str
    sources: tuple            # accepted event / evidence ids, never raw logs
    accepted_by: str          # "controller" or "human"
    accepted_at: float


class AcceptedLog:
    """Append-only JSONL of accepted facts; durable across restarts and hosts."""

    def __init__(self, path):
        self.path = path

    def append(self, fact):
        if not fact.sources:
            raise ValueError("an accepted fact needs at least one accepted source")
        if fact.accepted_by not in ("controller", "human"):
            raise ValueError("only the controller or a human can accept")
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(fact)) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def facts(self, workkey=None):
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as handle:
            items = [AcceptedFact(**{**json.loads(line), "sources": tuple(json.loads(line)["sources"])})
                     for line in handle if line.strip()]
        return [f for f in items if workkey is None or f.workkey == workkey]


@dataclass
class Checkpoint:
    workkey: str
    plan: list                     # ordered step names
    last_accepted_step: int = -1
    attempted: dict = field(default_factory=dict)   # step -> {"effect_class", "effect_confirmed"}
    grant_ids: list = field(default_factory=list)
    lease_scope: str = ""
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def from_log(cls, workkey, plan, log, **kw):
        steps = [f.step for f in log.facts(workkey)]
        return cls(workkey=workkey, plan=plan, last_accepted_step=max(steps) if steps else -1, **kw)


def decide(checkpoint, *, grants_valid, owned_alive, lease_available):
    """grants_valid: {grant_id: bool}; owned_alive: list of still-running owned pids;
    lease_available: whether this host can take the scope's write lease now."""
    reasons = []
    next_step = checkpoint.last_accepted_step + 1
    if next_step >= len(checkpoint.plan):
        # A finished plan is not a reason to start again at step 0, and a
        # still-running owned process is not a clean completion.
        if owned_alive:
            return {"safe": False, "resume_step": None, "state": "RECOVERING",
                    "reasons": [f"owned processes still running: {owned_alive}; retire or reattach first"]}
        return {"safe": True, "resume_step": None, "state": "DONE", "reasons": ["all steps accepted"]}
    attempt = checkpoint.attempted.get(next_step) or checkpoint.attempted.get(str(next_step))
    if attempt and attempt.get("effect_class") == "non_idempotent" and not attempt.get("effect_confirmed"):
        return {"safe": False, "resume_step": next_step, "state": "NEEDS_USER",
                "reasons": [f"step {next_step} may have had an effect; confirmation required before retry"]}
    expired = [g for g in checkpoint.grant_ids if not grants_valid.get(g, False)]
    if expired:
        return {"safe": False, "resume_step": next_step, "state": "NEEDS_USER",
                "reasons": [f"authority no longer valid: {expired}"]}
    if owned_alive:
        return {"safe": False, "resume_step": next_step, "state": "RECOVERING",
                "reasons": [f"owned processes still running: {owned_alive}; retire or reattach first"]}
    if not lease_available:
        return {"safe": False, "resume_step": next_step, "state": "WAITING",
                "reasons": ["another holder has the write lease"]}
    reasons.append(f"steps 0..{checkpoint.last_accepted_step} accepted; step {next_step} is safe to (re)run")
    return {"safe": True, "resume_step": next_step, "state": "RUNNING", "reasons": reasons}
