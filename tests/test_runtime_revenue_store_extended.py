import json
import pytest
from courier_runtime.revenue import (
    CONTACTED,
    DRAFT_READY,
    LOST,
    PROPOSAL,
    QUALIFIED,
    REPLIED,
    WAITING_FOR_HUMAN,
    WON,
    Job,
    Lead,
)
from courier_runtime.revenue_store import RevenueStore, main

def test_revenue_store_empty_directory_handling(tmp_path):
    store = RevenueStore(tmp_path / "fresh_sub_dir")
    assert store.leads() == []
    assert store.jobs() == []
    dash = store.dashboard("2026-10")
    assert dash["paid_revenue_eur"] == 0.0
    assert dash["direct_cost_eur"] == 0.0
    assert dash["leads_by_state"] == {}

def test_revenue_store_corrupted_and_blank_lines(tmp_path):
    store = RevenueStore(tmp_path)
    store.save_lead(Lead("L-1", "Org1", "Pain1", "Source1"))
    
    # Inject corruptions: blank lines, truncated JSON, non-JSON text
    with open(store.leads_path, "a", encoding="utf-8") as f:
        f.write("\n")
        f.write("NOT_JSON_DATA_HERE\n")
        f.write('{"lead_id": "truncated-line\n')
        f.write("\n")
    
    store.save_lead(Lead("L-2", "Org2", "Pain2", "Source2"))
    
    loaded_leads = store.leads()
    assert len(loaded_leads) == 2
    assert {l.lead_id for l in loaded_leads} == {"L-1", "L-2"}

def test_revenue_store_dashboard_complex_lead_states(tmp_path):
    store = RevenueStore(tmp_path)
    # Add leads across all distinct states
    states = [QUALIFIED, DRAFT_READY, WAITING_FOR_HUMAN, CONTACTED, REPLIED, PROPOSAL, WON, LOST]
    for idx, st in enumerate(states):
        l = Lead(f"L-{idx}", f"Org-{idx}", "Pain", "Src", state=st)
        store.save_lead(l)
    
    dash = store.dashboard("2026-10")
    for st in states:
        assert dash["leads_by_state"][st] == 1

def test_revenue_store_jobs_without_delivered_on_fallback(tmp_path):
    store = RevenueStore(tmp_path)
    # Job has paid_on but no delivered_on; cost and revenue both land in paid_on month
    job = Job(
        job_id="J-no-deliv",
        customer="Acme",
        offer="Audit",
        price_eur=500.0,
        paid=True,
        delivered=True,
        model_cost_eur=20.0,
        paid_on="2026-10-15",
        delivered_on="",
    )
    store.save_job(job)
    
    dash = store.dashboard("2026-10")
    assert dash["paid_revenue_eur"] == 500.0
    assert dash["direct_cost_eur"] == 20.0
    assert dash["contribution_eur"] == 480.0

def test_revenue_store_jobs_without_any_dates_omitted(tmp_path):
    store = RevenueStore(tmp_path)
    job = Job(
        job_id="J-undated",
        customer="Pending Inc",
        offer="Draft Plan",
        price_eur=300.0,
        paid=False,
        delivered=False,
        paid_on="",
        delivered_on="",
    )
    store.save_job(job)
    
    dash = store.dashboard("2026-10")
    assert dash["paid_revenue_eur"] == 0.0
    assert dash["direct_cost_eur"] == 0.0

def test_cli_dashboard_custom_monthly_cost(tmp_path, capsys):
    store = RevenueStore(tmp_path)
    store.save_job(Job(
        job_id="J-cost",
        customer="BigCorp",
        offer="Enterprise",
        price_eur=1000.0,
        paid=True,
        delivered=True,
        model_cost_eur=100.0,
        paid_on="2026-10-01",
        delivered_on="2026-10-01",
    ))
    # Execute CLI with --monthly-cost 900
    ret = main(["dashboard", "--home", str(tmp_path), "--month", "2026-10", "--monthly-cost", "900"])
    assert ret == 0
    out = json.loads(capsys.readouterr().out)
    assert out["monthly_cost_eur"] == 900.0
    assert out["contribution_eur"] == 900.0
    assert out["self_funding_pct"] == 100.0
