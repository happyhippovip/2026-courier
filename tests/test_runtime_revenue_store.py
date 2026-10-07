import json

from courier_runtime.revenue import DRAFT_READY, QUALIFIED, Job, Lead
from courier_runtime.revenue_store import RevenueStore, main


def test_last_snapshot_wins_and_history_survives(tmp_path):
    store = RevenueStore(tmp_path)
    lead = Lead("L1", "Example Studio", "CI red for 3 weeks", "public issue")
    store.save_lead(lead)
    lead.move(QUALIFIED, 1)
    lead.move(DRAFT_READY, 2)
    store.save_lead(lead)
    [loaded] = store.leads()
    assert loaded.state == DRAFT_READY and len(loaded.history) == 2
    assert len(store.leads_path.read_text().splitlines()) == 2      # append-only


def test_torn_last_line_is_skipped(tmp_path):
    store = RevenueStore(tmp_path)
    store.save_job(Job("J1", "A", "repo-reality-check", 149))
    with open(store.jobs_path, "a") as f:
        f.write('{"job_id": "J2", "custo')
    assert [j.job_id for j in store.jobs()] == ["J1"]


def test_dashboard_counts_revenue_in_the_month_it_was_paid(tmp_path):
    store = RevenueStore(tmp_path)
    store.save_job(Job("J1", "A", "rrc", 149, paid=True, delivered=True, model_cost_eur=5,
                       paid_on="2026-10-12", delivered_on="2026-10-10"))
    store.save_job(Job("J2", "B", "rrc", 149, paid=True, delivered=True, model_cost_eur=5,
                       paid_on="2026-11-02", delivered_on="2026-10-30"))
    store.save_job(Job("J3", "C", "rrc", 149, paid=True, delivered=True, paid_on="2026-09-01",
                       delivered_on="2026-09-01"))
    oct_ = store.dashboard("2026-10")
    assert oct_["paid_revenue_eur"] == 149 and oct_["direct_cost_eur"] == 10
    assert oct_["jobs_unpaid_delivered"] == 1 and oct_["self_funding_pct"] == 76.0
    nov = store.dashboard("2026-11")
    assert nov["paid_revenue_eur"] == 149 and nov["direct_cost_eur"] == 0     # J2's cost stays in October


def test_cli_dashboard(tmp_path, capsys):
    RevenueStore(tmp_path).save_lead(Lead("L1", "X", "p", "s"))
    assert main(["dashboard", "--home", str(tmp_path), "--month", "2026-10"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["paid_revenue_eur"] == 0 and out["leads_by_state"] == {"PROSPECT": 1}
