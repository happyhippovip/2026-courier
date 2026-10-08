import pytest
from courier_runtime.revenue import (
    CONTACTED,
    DRAFT_READY,
    LOST,
    PROPOSAL,
    PROSPECT,
    QUALIFIED,
    REPLIED,
    WAITING_FOR_HUMAN,
    WON,
    Job,
    Lead,
    LeadError,
    SpendGrant,
    check_spend,
    self_funding,
)

def test_lead_all_illegal_shortcuts_rejected():
    l = Lead("L-edge", "Org", "Pain", "Source")
    # Illegal jumps from PROSPECT
    for bad_state in [DRAFT_READY, WAITING_FOR_HUMAN, CONTACTED, REPLIED, PROPOSAL, WON]:
        with pytest.raises(LeadError):
            l.move(bad_state, 1, human_approval="lead-ok")
    
    # Progress to QUALIFIED
    l.move(QUALIFIED, 2)
    for bad_state in [WAITING_FOR_HUMAN, CONTACTED, REPLIED, PROPOSAL, WON]:
        with pytest.raises(LeadError):
            l.move(bad_state, 3, human_approval="lead-ok")

def test_lead_redraft_and_counter_offer_loops():
    l = Lead("L-loop", "Org", "Pain", "Source")
    l.move(QUALIFIED, 1)
    l.move(DRAFT_READY, 2)
    l.move(WAITING_FOR_HUMAN, 3)
    
    # Human asks for a redraft
    l.move(DRAFT_READY, 4, note="tone too aggressive")
    assert l.state == DRAFT_READY
    
    # Ready again
    l.move(WAITING_FOR_HUMAN, 5)
    l.move(CONTACTED, 6, human_approval="human-ok-1")
    l.move(REPLIED, 7)
    
    # Human re-review loop from REPLIED
    l.move(WAITING_FOR_HUMAN, 8)
    l.move(CONTACTED, 9, human_approval="human-ok-2")
    l.move(REPLIED, 10)
    
    # Move to proposal
    l.move(PROPOSAL, 11, human_approval="human-ok-3")
    # Counter-offer review loop
    l.move(WAITING_FOR_HUMAN, 12)
    assert l.state == WAITING_FOR_HUMAN

def test_lead_won_is_strictly_terminal():
    l = Lead("L-won", "Org", "Pain", "Source")
    l.move(QUALIFIED, 1)
    l.move(DRAFT_READY, 2)
    l.move(WAITING_FOR_HUMAN, 3)
    l.move(CONTACTED, 4, human_approval="appr-1")
    l.move(REPLIED, 5)
    l.move(PROPOSAL, 6, human_approval="appr-2")
    l.move(WON, 7, human_approval="appr-3")
    
    for any_state in [PROSPECT, QUALIFIED, DRAFT_READY, WAITING_FOR_HUMAN, CONTACTED, REPLIED, PROPOSAL, LOST]:
        with pytest.raises(LeadError):
            l.move(any_state, 8, human_approval="appr-4")

def test_job_detailed_direct_cost_breakdown():
    j = Job(
        job_id="J-comp",
        customer="Client A",
        offer="Full Stack Audit",
        price_eur=1000.0,
        paid=True,
        delivered=True,
        model_cost_eur=12.50,
        cloud_cost_eur=25.00,
        api_cost_eur=5.25,
        other_direct_cost_eur=7.25,
        human_minutes=45,
        execution_minutes=120,
        reworks=2,
        failed=False,
    )
    assert j.direct_cost_eur == 50.00
    assert j.revenue_eur == 1000.0
    assert j.contribution_eur == 950.00

def test_self_funding_empty_and_zero_baseline():
    empty_res = self_funding([], monthly_cost_eur=200.0)
    assert empty_res["paid_revenue_eur"] == 0.0
    assert empty_res["direct_cost_eur"] == 0.0
    assert empty_res["contribution_eur"] == 0.0
    assert empty_res["self_funding_pct"] == 0.0
    assert empty_res["failure_rate"] is None
    assert empty_res["rework_per_job"] is None

    # monthly_cost_eur = 0
    zero_cost_res = self_funding([], monthly_cost_eur=0.0)
    assert zero_cost_res["self_funding_pct"] is None

def test_spend_grant_exact_boundary_conditions():
    grant = SpendGrant("sg-bound", "acct-ci", "cloud", "hetzner", 100.0, 1000.0, 2000.0)
    # Exact start timestamp: allowed (start <= at < end)
    assert check_spend(grant, "acct-ci", "cloud", "hetzner", 50.0, 0.0, at=1000.0) == []
    # Exact end timestamp: refused
    assert any("outside the granted time window" in err for err in check_spend(grant, "acct-ci", "cloud", "hetzner", 50.0, 0.0, at=2000.0))
    # Just before end timestamp: allowed
    assert check_spend(grant, "acct-ci", "cloud", "hetzner", 50.0, 0.0, at=1999.99) == []
    
    # Exact max spend saturation: allowed (100.0 == 100.0)
    assert check_spend(grant, "acct-ci", "cloud", "hetzner", 100.0, 0.0, at=1500.0) == []
    # 0.01 over max spend: refused
    assert any("would exceed max spend" in err for err in check_spend(grant, "acct-ci", "cloud", "hetzner", 100.01, 0.0, at=1500.0))
