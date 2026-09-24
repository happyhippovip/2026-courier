import json
import pytest
from pathlib import Path

from scripts.execute_p01_transmission import transmit_p01, main


@pytest.fixture
def spec_file(tmp_path: Path) -> Path:
    p = tmp_path / "FINAL_P01_FOLLOWUP_SPEC.json"
    data = {
        "opportunity_id": "OPP-P01",
        "current_status": "WAITING_FOR_HUMAN",
        "message_fingerprint": "sha256-mock-fingerprint-12345",
        "customer": "chief_pilot"
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_transmit_p01_success(spec_file: Path):
    res = transmit_p01(spec_path=spec_file)
    assert res is not None
    assert res["current_status"] == "TRANSMITTED_BY_CHIEF"
    assert "transmitted_at" in res

    # Verify disk was updated
    disk_data = json.loads(spec_file.read_text(encoding="utf-8"))
    assert disk_data["current_status"] == "TRANSMITTED_BY_CHIEF"
    assert disk_data["transmitted_at"] == res["transmitted_at"]


def test_transmit_p01_already_transmitted(spec_file: Path):
    # First transmission
    res1 = transmit_p01(spec_path=spec_file)
    assert res1["current_status"] == "TRANSMITTED_BY_CHIEF"
    t1 = res1["transmitted_at"]

    # Second transmission should not re-transmit
    res2 = transmit_p01(spec_path=spec_file)
    assert res2["current_status"] == "TRANSMITTED_BY_CHIEF"
    assert res2["transmitted_at"] == t1


def test_transmit_p01_file_not_found(tmp_path: Path):
    res = transmit_p01(spec_path=tmp_path / "missing.json")
    assert res is None


def test_transmit_p01_cli(spec_file: Path, capsys):
    code = main(["--spec-path", str(spec_file), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "SUCCESS"
    assert data["current_status"] == "TRANSMITTED_BY_CHIEF"
    assert data["message_fingerprint"] == "sha256-mock-fingerprint-12345"

    # Missing file returns 1
    code_missing = main(["--spec-path", str(spec_file.parent / "nonexistent.json"), "--json"])
    assert code_missing == 1
