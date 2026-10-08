import pytest
from courier_runtime.revenue import (
    Lead,
    Job,
    SpendGrant,
    check_spend,
    self_funding,
    WAITING_FOR_HUMAN,
    DRAFT_READY,
    REPLIED,
    PROPOSAL,
    LOST,
    LeadError,
)


def test_lead_redraft_and_drop_from_waiting_for_human():
    lead = Lead("L-test", "Org", "Build broken", "Issue #1")
    lead.move("QUALIFIED", 1)
    lead.move("DRAFT_READY", 2)
    lead.move("WAITING_FOR_HUMAN", 3)

    # Human requests redraft
    lead.move("DRAFT_READY", 4, note="Fix tone")
    assert lead.state == "DRAFT_READY"

    # Back to waiting for human
    lead.move("WAITING_FOR_HUMAN", 5)

    # Human drops lead
    lead.move("LOST", 6, note="Not a fit")
    assert lead.state == "LOST"


def test_job_direct_cost_and_contribution():
    job = Job(
        job_id="J-100",
        customer="Client A",
        offer="Audit",
        price_eur=500.0,
        paid=True,
        delivered=True,
        model_cost_eur=10.0,
        cloud_cost_eur=5.0,
        api_cost_eur=15.0,
        other_direct_cost_eur=20.0,
    )
    assert job.direct_cost_eur == 50.0
    assert job.revenue_eur == 500.0
    assert job.contribution_eur == 450.0


def test_check_spend_all_bounds():
    grant = SpendGrant(
        grant_id="sg-1",
        account="acct-main",
        purpose="api",
        service="anthropic",
        max_spend_eur=100.0,
        start=1000.0,
        end=2000.0,
        revoked=False,
    )

    # No grant
    assert "no spend grant" in check_spend(None, "acct-main", "api", "anthropic", 10.0, 0.0, 1500.0)[0]

    # Outside time window
    errs = check_spend(grant, "acct-main", "api", "anthropic", 10.0, 0.0, 999.0)
    assert any("outside the granted time window" in e for e in errs)

    # Revoked grant
    revoked_grant = SpendGrant(
        grant_id="sg-2",
        account="acct-main",
        purpose="api",
        service="anthropic",
        max_spend_eur=100.0,
        start=1000.0,
        end=2000.0,
        revoked=True,
    )
    assert any("grant revoked" in e for e in check_spend(revoked_grant, "acct-main", "api", "anthropic", 10.0, 0.0, 1500.0))

    # Wrong account / purpose / service
    mismatches = check_spend(grant, "wrong-acct", "wrong-purpose", "wrong-service", 10.0, 0.0, 1500.0)
    assert any("account 'wrong-acct' not granted" in e for e in mismatches)
    assert any("purpose 'wrong-purpose' not granted" in e for e in mismatches)
    assert any("service 'wrong-service' not granted" in e for e in mismatches)

    # Non-positive amount
    assert any("amount must be positive" in e for e in check_spend(grant, "acct-main", "api", "anthropic", 0.0, 0.0, 1500.0))
    assert any("amount must be positive" in e for e in check_spend(grant, "acct-main", "api", "anthropic", -5.0, 0.0, 1500.0))

    # Exceeds max spend
    exceeds = check_spend(grant, "acct-main", "api", "anthropic", 60.0, 50.0, 1500.0)
    assert any("would exceed max spend 100.0 EUR" in e for e in exceeds)

    # Fits grant perfectly
    assert check_spend(grant, "acct-main", "api", "anthropic", 40.0, 50.0, 1500.0) == []
