"""Provider-neutral adapter core and the campaign authority boundary.

An adapter declares, per version and immutably, what it can do and with which
effect class. Every call goes REQUEST -> GRANT -> EXECUTE -> RESULT -> EVIDENCE.
A capability the adapter did not declare is refused; authority comes only
from the Permission Broker; an uncertain external effect is never retried
automatically. No network, credentials or spending live here.
"""
from dataclasses import dataclass, field

from courier_runtime.grants import GRANTED, Request

FAILURE_CLASSES = {"transient", "auth_expired", "denied", "uncertain_effect"}


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    version: str
    capabilities: dict            # capability -> effect class


@dataclass
class CallResult:
    status: str                   # DONE | NEEDS_USER | REFUSED | FAILED
    evidence: dict = field(default_factory=dict)
    failure: str | None = None
    retry_eligible: bool = False
    reason: str = ""


def call(spec, broker, request, execute):
    """execute(request) -> (ok: bool, evidence: dict, failure_class: str|None)."""
    declared = spec.capabilities.get(request.capability)
    if declared is None:
        return CallResult("REFUSED", reason=f"{spec.adapter_id} did not declare {request.capability}")
    if declared != request.effect_class:
        return CallResult("REFUSED", reason=f"{request.capability} is {declared}, not {request.effect_class}")
    grant, state, reason = broker.authorize(request)
    if state != GRANTED:
        return CallResult("NEEDS_USER", reason=f"authority required: {reason}")
    ok, evidence, failure = execute(request)
    if ok:
        return CallResult("DONE", evidence={**evidence, "grant_id": grant.grant_id,
                                            "adapter": f"{spec.adapter_id}@{spec.version}"})
    if failure not in FAILURE_CLASSES:
        failure = "uncertain_effect"            # unknown failure: assume an effect may have happened
    retry = failure == "transient" and declared == "idempotent"
    status = "NEEDS_USER" if failure in ("auth_expired", "uncertain_effect") else "FAILED"
    return CallResult(status, evidence=evidence, failure=failure, retry_eligible=retry, reason=failure)


# -- Promote / Launch campaign -------------------------------------------------

@dataclass(frozen=True)
class CampaignGrant:
    grant_id: str
    ad_account: str
    channel: str
    creative_hash: str
    audience_hash: str
    regions: frozenset
    daily_budget_cap: float
    total_budget_cap: float
    start: float
    end: float
    allowed_actions: frozenset    # subset of {"create", "pause", "resume"}


@dataclass(frozen=True)
class CampaignPlan:
    ad_account: str
    channel: str
    creative_hash: str
    audience_hash: str
    regions: frozenset
    daily_budget: float
    total_budget: float
    start: float
    end: float


def promote(plan):
    """PREPARE + PREVIEW only: no effect, no grant needed."""
    days = max(1.0, (plan.end - plan.start) / 86400)
    return {"effect": None, "preview": {"account": plan.ad_account, "channel": plan.channel,
                                        "regions": sorted(plan.regions),
                                        "max_spend": min(plan.total_budget, plan.daily_budget * days)}}


def check_launch(plan, grant, action="create"):
    """Return [] if the action fits inside the grant, else every violated dimension."""
    if grant is None:
        return ["no campaign grant: Launch needs explicit, bounded authority"]
    v = []
    if action not in grant.allowed_actions:
        v.append(f"action {action} not granted")
    if action == "pause":
        return v                                    # narrowing is always within authority
    for dim in ("ad_account", "channel", "creative_hash", "audience_hash"):
        if getattr(plan, dim) != getattr(grant, dim):
            v.append(f"{dim} changed")
    if not plan.regions <= grant.regions:
        v.append(f"regions {sorted(plan.regions - grant.regions)} not granted")
    if plan.daily_budget > grant.daily_budget_cap:
        v.append("daily budget above cap")
    if plan.total_budget > grant.total_budget_cap:
        v.append("total budget above cap")
    if plan.start < grant.start or plan.end > grant.end:
        v.append("duration outside the granted window")
    return v
