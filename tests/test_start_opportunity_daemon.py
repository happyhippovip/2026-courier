import json
import pytest
from pathlib import Path

from scripts.start_opportunity_daemon import load_live_opportunities, main


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "opp_repo"
    repo.mkdir()
    mi_dir = repo / "events" / "revenue-opportunities" / "market_intelligence"
    mi_dir.mkdir(parents=True)

    exp1 = {
        "experiment_id": "EXP-001",
        "price_eur": 199.0,
        "target_offering": "COURIER_AUDIT_PRO",
        "evidence_class": "SOURCE_SUPPORTED_PAIN_PATTERN",
        "public_source": "Reddit",
        "observed_pain": "Manual deployment delays",
        "source_date": "2026-09-24",
        "buyer_role": "Engineering Lead",
        "message_body": {
            "subject": "Audit Offering"
        }
    }
    (mi_dir / "MARKET_EXPERIMENT_001.json").write_text(json.dumps(exp1), encoding="utf-8")

    exp2 = {
        "experiment_id": "EXP-002",
        "price_eur": 49.0,
        "target_offering": "KIBEY_PLUGIN",
        "evidence_class": "OTHER",
        "public_source": "Twitter",
        "observed_pain": "Video editing complexity",
        "source_date": "2026-09-23",
        "buyer_role": "Creator"
    }
    (mi_dir / "MARKET_EXPERIMENT_002.json").write_text(json.dumps(exp2), encoding="utf-8")

    return repo


def test_load_live_opportunities_empty(tmp_path: Path):
    opps = load_live_opportunities(repo_dir=tmp_path)
    assert opps == []


def test_load_live_opportunities(mock_repo: Path):
    opps = load_live_opportunities(repo_dir=mock_repo)
    assert len(opps) == 2

    def get_val(item, key):
        if isinstance(item, dict):
            return item[key]
        return getattr(item, key)

    opp1 = next(o for o in opps if get_val(o, "opportunity_id") == "EXP-001")
    domain1 = get_val(opp1, "domain")
    domain1_str = domain1.name if hasattr(domain1, "name") else domain1
    assert domain1_str == "B2B_AUTOMATION"
    assert get_val(opp1, "expected_revenue_eur") == 199.0

    opp2 = next(o for o in opps if get_val(o, "opportunity_id") == "EXP-002")
    domain2 = get_val(opp2, "domain")
    domain2_str = domain2.name if hasattr(domain2, "name") else domain2
    assert domain2_str == "SOFTWARE"
    assert get_val(opp2, "expected_revenue_eur") == 49.0


def test_start_opportunity_daemon_cli_empty(tmp_path: Path, capsys):
    code = main(["--repo-dir", str(tmp_path), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "NO_OPPORTUNITIES_FOUND"
    assert data["loaded_count"] == 0


def test_start_opportunity_daemon_cli_with_opps(mock_repo: Path, capsys):
    code = main(["--repo-dir", str(mock_repo), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data.get("status") in ("DEPENDENCY_UNAVAILABLE", "COMPLETED") or "cycle_id" in data
