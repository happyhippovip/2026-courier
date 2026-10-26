import json

import pytest

from courier_runtime.revenue import DRAFT_READY, QUALIFIED, Job, Lead
from courier_runtime.revenue_store import RevenueStore, main


def test_revenue_store_refuses_a_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    home = tmp_path / "home"
    home.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        RevenueStore(home).save_lead(Lead("L1", "X", "p", "s"))
    assert not (outside / "revenue").exists()

    real = tmp_path / "real"
    real.mkdir()
    store = RevenueStore(real)
    store.dir.mkdir()
    planted = tmp_path / "stolen-leads.jsonl"
    planted.write_text('{"lead_id":"stolen"}\n', encoding="utf-8")
    store.leads_path.symlink_to(planted)
    with pytest.raises(OSError, match="symlink"):
        store.leads()
    assert planted.read_text(encoding="utf-8") == '{"lead_id":"stolen"}\n'


def test_revenue_store_refuses_a_home_two_levels_under_a_symlink(tmp_path):
    outside = tmp_path / "outside"
    (outside / "mid").mkdir(parents=True)
    (outside / "mid" / "SECRET").write_text("SECRET", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError, match="symlink"):
        RevenueStore(link / "mid").save_lead(Lead("L1", "X", "p", "s"))
    assert (outside / "mid" / "SECRET").read_text(encoding="utf-8") == "SECRET"
    assert not (outside / "mid" / "revenue").exists()

    real = tmp_path / "real"
    store = RevenueStore(real)
    store.save_lead(Lead("L1", "Example", "note", "src"))
    assert store.leads()[0].lead_id == "L1"



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
