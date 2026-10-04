import pytest

from courier_runtime.revenue import (CONTACTED, DRAFT_READY, LOST, PROPOSAL, QUALIFIED, REPLIED,
                                     WAITING_FOR_HUMAN, WON, Job, Lead, LeadError, SpendGrant,
                                     check_spend, self_funding)


def lead():
    return Lead("L1", "Example Studio", "CI red on main for 3 weeks; tests pass locally", "public repo issue #12")


def test_lead_reaches_won_only_through_human_gates():
    l = lead()
    l.move(QUALIFIED, 1)
    l.move(DRAFT_READY, 2)
    l.move(WAITING_FOR_HUMAN, 3)
    l.move(CONTACTED, 4, human_approval="dennis-ok-1")
    l.move(REPLIED, 5)
    l.move(PROPOSAL, 6, human_approval="dennis-ok-2")
    l.move(WON, 7, human_approval="dennis-ok-3")
    assert [h["to"] for h in l.history][-1] == WON
    assert all(h["approval"] for h in l.history if h["to"] in (CONTACTED, PROPOSAL, WON))


def test_no_contact_without_approval_or_review():
    l = lead()
    l.move(QUALIFIED, 1)
    l.move(DRAFT_READY, 2)
    with pytest.raises(LeadError):
        l.move(CONTACTED, 3, human_approval="x")          # skipped the human review state
    l.move(WAITING_FOR_HUMAN, 3)
    with pytest.raises(LeadError):
        l.move(CONTACTED, 4)                                # no approval id
    with pytest.raises(LeadError):
        l.move(WON, 4, human_approval="x")                  # illegal jump


def test_lost_is_terminal():
    l = lead()
    l.move(LOST, 1)
    with pytest.raises(LeadError):
        l.move(QUALIFIED, 2)


def test_unpaid_work_is_never_revenue_and_metric_matches_definition():
    jobs = [Job("J1", "A", "repo-reality-check", 149, paid=True, delivered=True, model_cost_eur=4.5, cloud_cost_eur=0.5),
            Job("J2", "B", "repo-reality-check", 149, paid=True, delivered=True, model_cost_eur=6.0, reworks=1),
            Job("J3", "C", "repo-reality-check", 149, paid=False, delivered=True, model_cost_eur=5.0)]
    m = self_funding(jobs, monthly_cost_eur=183)
    assert m["paid_revenue_eur"] == 298 and m["direct_cost_eur"] == 16.0
    assert m["contribution_eur"] == 282.0 and m["self_funding_pct"] == 154.1
    assert m["jobs_unpaid_delivered"] == 1 and m["rework_per_job"] == 0.33
    assert jobs[2].contribution_eur == -5.0


def test_negative_contribution_shows_zero_self_funding():
    m = self_funding([Job("J", "A", "x", 50, paid=True, delivered=True, api_cost_eur=80)], 183)
    assert m["contribution_eur"] == -30 and m["self_funding_pct"] == 0.0


GRANT = SpendGrant("sg1", "acct-ads", "ads", "search-ads", 30.0, 0.0, 100.0)


def test_spend_inside_grant_is_allowed():
    assert check_spend(GRANT, "acct-ads", "ads", "search-ads", 10, 15, 50) == []


@pytest.mark.parametrize("kw, already", [
    (dict(amount_eur=20), 15),                       # exceeds max
    (dict(account="acct-other"), 0),
    (dict(purpose="subscription"), 0),
    (dict(service="social-ads"), 0),
    (dict(at=150), 0),                                # outside window
    (dict(amount_eur=0), 0),
])
def test_spend_outside_grant_is_refused(kw, already):
    args = dict(account="acct-ads", purpose="ads", service="search-ads", amount_eur=10, at=50)
    args.update(kw)
    assert check_spend(GRANT, already_spent_eur=already, **args)


def test_no_grant_or_revoked_grant_means_no_spend():
    assert check_spend(None, "a", "ads", "s", 1, 0, 1)
    from dataclasses import replace
    assert check_spend(replace(GRANT, revoked=True), "acct-ads", "ads", "search-ads", 1, 0, 50)
