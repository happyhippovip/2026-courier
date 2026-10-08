import pytest

from courier_runtime.revenue import (
    PROSPECT,
    QUALIFIED,
    DRAFT_READY,
    WAITING_FOR_HUMAN,
    CONTACTED,
    REPLIED,
    PROPOSAL,
    WON,
    LOST,
    Job,
    Lead,
    LeadError,
    SpendGrant,
    check_spend,
    self_funding,
)


def test_lead_redraft_loop_and_drop_to_lost():
    l = Lead("L-redraft", "Client Corp", "Slow flaky CI pipeline", "github.com/issue/1")
    l.move(QUALIFIED, 1)
    l.move(DRAFT_READY, 2)
    l.move(WAITING_FOR_HUMAN, 3)

    # Human requests redraft
    l.move(DRAFT_READY, 4, note="Tone too formal, make it friendly")
    assert l.state == DRAFT_READY

    # Re-submit to human
    l.move(WAITING_FOR_HUMAN, 5)
    # Human approves
    l.move(CONTACTED, 6, human_approval="appr-101")
    assert l.state == CONTACTED

    # Can drop to LOST at any point
    l.move(LOST, 7, note="Client solved issue in-house")
    assert l.state == LOST


def test_won_is_strictly_terminal():
    l = Lead("L-won", "Happy Client", "Flaky DB transactions", "referral")
    l.move(QUALIFIED, 1)
    l.move(DRAFT_READY, 2)
    l.move(WAITING_FOR_HUMAN, 3)
    l.move(CONTACTED, 4, human_approval="appr-1")
    l.move(REPLIED, 5)
    l.move(PROPOSAL, 6, human_approval="appr-2")
    l.move(WON, 7, human_approval="appr-3")

    with pytest.raises(LeadError, match="not allowed"):
        l.move(LOST, 8)
    with pytest.raises(LeadError, match="not allowed"):
        l.move(PROSPECT, 8)


def test_job_unit_economics_aggregation():
    job = Job(
        job_id="J-costs",
        customer="Acme Corp",
        offer="diagnostic-sweep",
        price_eur=500.0,
        paid=True,
        delivered=True,
        model_cost_eur=12.50,
        cloud_cost_eur=4.25,
        api_cost_eur=2.15,
        other_direct_cost_eur=1.10,
        reworks=2,
        failed=False,
    )

    assert job.revenue_eur == 500.0
    assert round(job.direct_cost_eur, 2) == 20.00
    assert job.contribution_eur == 480.00


def test_self_funding_metric_empty_and_zero_cost():
    # Empty job list
    empty_stats = self_funding([], monthly_cost_eur=200.0)
    assert empty_stats["paid_revenue_eur"] == 0.0
    assert empty_stats["direct_cost_eur"] == 0.0
    assert empty_stats["contribution_eur"] == 0.0
    assert empty_stats["self_funding_pct"] == 0.0
    assert empty_stats["failure_rate"] is None
    assert empty_stats["rework_per_job"] is None

    # Zero monthly cost returns None for percentage
    zero_cost_stats = self_funding([], monthly_cost_eur=0.0)
    assert zero_cost_stats["self_funding_pct"] is None


def test_check_spend_boundary_and_multi_violations():
    grant = SpendGrant("grant-edge", "acct-test", "cloud", "aws", 100.0, 10.0, 50.0)

    # Exact boundary start timestamp is valid: start <= at < end
    assert check_spend(grant, "acct-test", "cloud", "aws", 20.0, 0.0, at=10.0) == []

    # Exact boundary end timestamp is outside window
    v_end = check_spend(grant, "acct-test", "cloud", "aws", 20.0, 0.0, at=50.0)
    assert "outside the granted time window" in v_end

    # Exact spend capacity limit: already 80 + amount 20 == 100 max
    assert check_spend(grant, "acct-test", "cloud", "aws", 20.0, 80.0, at=25.0) == []

    # Exceeding capacity by 0.01
    v_exceed = check_spend(grant, "acct-test", "cloud", "aws", 20.01, 80.0, at=25.0)
    assert any("would exceed max spend" in err for err in v_exceed)

    # Negative amount
    v_neg = check_spend(grant, "acct-test", "cloud", "aws", -5.0, 0.0, at=25.0)
    assert "amount must be positive" in v_neg

    # Multiple simultaneous violations
    v_multi = check_spend(grant, "wrong-acct", "wrong-purpose", "wrong-service", 0.0, 100.0, at=99.0)
    assert len(v_multi) >= 4
