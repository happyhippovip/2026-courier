import json
from pathlib import Path
from courier_runtime.revenue import Job, Lead
from courier_runtime.revenue_store import RevenueStore


def test_empty_store_returns_empty_lists(tmp_path):
    store = RevenueStore(tmp_path)
    assert store.leads() == []
    assert store.jobs() == []
    dash = store.dashboard("2026-10")
    assert dash["paid_revenue_eur"] == 0.0
    assert dash["direct_cost_eur"] == 0.0
    assert dash["contribution_eur"] == 0.0
    assert dash["self_funding_pct"] == 0.0
    assert dash["leads_by_state"] == {}


def test_dashboard_delivered_only_cost_counted(tmp_path):
    store = RevenueStore(tmp_path)
    # Job delivered in October, but not paid yet
    store.save_job(
        Job(
            job_id="J-oct-deliv",
            customer="Acme Corp",
            offer="Security Review",
            price_eur=1000.0,
            paid=False,
            delivered=True,
            model_cost_eur=25.0,
            delivered_on="2026-10-15",
        )
    )
    dash = store.dashboard("2026-10")
    assert dash["paid_revenue_eur"] == 0.0
    assert dash["direct_cost_eur"] == 25.0
    assert dash["contribution_eur"] == -25.0
    assert dash["jobs_unpaid_delivered"] == 1


def test_dashboard_leads_state_aggregation(tmp_path):
    store = RevenueStore(tmp_path)
    l1 = Lead("L1", "Org1", "prob1", "src1", state="PROSPECT")
    l2 = Lead("L2", "Org2", "prob2", "src2", state="QUALIFIED")
    l3 = Lead("L3", "Org3", "prob3", "src3", state="QUALIFIED")
    l4 = Lead("L4", "Org4", "prob4", "src4", state="WON")
    store.save_lead(l1)
    store.save_lead(l2)
    store.save_lead(l3)
    store.save_lead(l4)

    dash = store.dashboard("2026-10")
    assert dash["leads_by_state"] == {
        "PROSPECT": 1,
        "QUALIFIED": 2,
        "WON": 1,
    }
