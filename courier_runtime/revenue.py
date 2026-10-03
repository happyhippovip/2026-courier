"""Revenue engine core: leads with a human gate, a job ledger with unit
economics, the self-funding metric, and a spend guard.

Revenue never silently becomes spending or contact: every outward step
(contacting a prospect, sending a proposal, accepting a job) needs a human
approval id, and any spend needs a bounded SpendGrant. Unpaid work is never
revenue. Pure logic; storage and adapters live elsewhere.
"""
from dataclasses import dataclass, field

PROSPECT, QUALIFIED, DRAFT_READY, WAITING_FOR_HUMAN = "PROSPECT", "QUALIFIED", "DRAFT_READY", "WAITING_FOR_HUMAN"
CONTACTED, REPLIED, PROPOSAL, WON, LOST = "CONTACTED", "REPLIED", "PROPOSAL", "WON", "LOST"

LEAD_TRANSITIONS = {
    PROSPECT: {QUALIFIED, LOST},
    QUALIFIED: {DRAFT_READY, LOST},
    DRAFT_READY: {WAITING_FOR_HUMAN, LOST},
    WAITING_FOR_HUMAN: {CONTACTED, DRAFT_READY, LOST},   # human approves the send, asks for a redraft, or drops
    CONTACTED: {REPLIED, LOST},
    REPLIED: {PROPOSAL, LOST, WAITING_FOR_HUMAN},
    PROPOSAL: {WON, LOST, WAITING_FOR_HUMAN},
    WON: set(), LOST: set(),
}
HUMAN_GATED = {CONTACTED, PROPOSAL, WON}   # outward or binding steps


class LeadError(Exception):
    pass


@dataclass
class Lead:
    lead_id: str
    organisation: str
    problem: str                  # the observed, specific pain - no generic blasts
    source: str                   # where the need was observed (public URL / referral)
    state: str = PROSPECT
    history: list = field(default_factory=list)

    def move(self, new_state, at, human_approval=None, note=""):
        if new_state not in LEAD_TRANSITIONS[self.state]:
            raise LeadError(f"{self.state} -> {new_state} is not allowed")
        if new_state in HUMAN_GATED and not human_approval:
            raise LeadError(f"{new_state} needs a human approval id")
        if new_state == CONTACTED and self.state != WAITING_FOR_HUMAN:
            raise LeadError("contact only after a human reviewed the draft")
        self.history.append({"from": self.state, "to": new_state, "at": at,
                             "approval": human_approval, "note": note})
        self.state = new_state


@dataclass
class Job:
    job_id: str
    customer: str
    offer: str
    price_eur: float
    paid: bool = False            # revenue only when the money arrived
    delivered: bool = False
    model_cost_eur: float = 0.0
    cloud_cost_eur: float = 0.0
    api_cost_eur: float = 0.0
    other_direct_cost_eur: float = 0.0
    human_minutes: int = 0
    execution_minutes: int = 0
    reworks: int = 0
    failed: bool = False
    evidence: list = field(default_factory=list)
    paid_on: str = ""             # ISO date the money arrived; groups revenue by month
    delivered_on: str = ""        # ISO date the report reached the customer

    @property
    def revenue_eur(self):
        return self.price_eur if self.paid else 0.0

    @property
    def direct_cost_eur(self):
        return self.model_cost_eur + self.cloud_cost_eur + self.api_cost_eur + self.other_direct_cost_eur

    @property
    def contribution_eur(self):
        return round(self.revenue_eur - self.direct_cost_eur, 2)


def self_funding(jobs, monthly_cost_eur):
    """The dashboard metric. 100% = contribution covers recurring Courier cost.
    Delivered-but-unpaid jobs count their cost, never their price."""
    revenue = round(sum(j.revenue_eur for j in jobs), 2)
    direct = round(sum(j.direct_cost_eur for j in jobs), 2)
    contribution = round(revenue - direct, 2)
    done = [j for j in jobs if j.delivered]
    return {
        "monthly_cost_eur": monthly_cost_eur, "paid_revenue_eur": revenue, "direct_cost_eur": direct,
        "contribution_eur": contribution,
        "self_funding_pct": round(100 * max(0.0, contribution) / monthly_cost_eur, 1) if monthly_cost_eur else None,
        "jobs_paid": sum(j.paid for j in jobs), "jobs_unpaid_delivered": sum(j.delivered and not j.paid for j in jobs),
        "failure_rate": round(sum(j.failed for j in done) / len(done), 2) if done else None,
        "rework_per_job": round(sum(j.reworks for j in done) / len(done), 2) if done else None,
        "human_minutes": sum(j.human_minutes for j in jobs),
    }


@dataclass(frozen=True)
class SpendGrant:
    grant_id: str
    account: str
    purpose: str                  # e.g. "ads", "cloud", "api", "subscription"
    service: str
    max_spend_eur: float
    start: float
    end: float
    revoked: bool = False


def check_spend(grant, account, purpose, service, amount_eur, already_spent_eur, at):
    """[] if the spend fits the grant, else every violated bound. No grant -> refused."""
    if grant is None:
        return ["no spend grant: Courier never spends without explicit bounded authority"]
    v = []
    if grant.revoked:
        v.append("grant revoked")
    if not grant.start <= at < grant.end:
        v.append("outside the granted time window")
    for name, got, want in (("account", account, grant.account), ("purpose", purpose, grant.purpose),
                            ("service", service, grant.service)):
        if got != want:
            v.append(f"{name} {got!r} not granted")
    if amount_eur <= 0:
        v.append("amount must be positive")
    if already_spent_eur + amount_eur > grant.max_spend_eur:
        v.append(f"would exceed max spend {grant.max_spend_eur} EUR")
    return v
