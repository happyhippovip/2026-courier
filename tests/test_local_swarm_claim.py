import json
import pytest
from pathlib import Path
from unittest.mock import patch

from scripts import local_swarm_claim


@pytest.fixture
def mock_swarm_env(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    state = root / ".courier_swarm"
    ops = root / "ops" / "ai"
    ops.mkdir(parents=True)
    bank_file = ops / "AUTO_SWARM_TASKBANK_2026-09-28.json"

    taskbank = {
        "tasks": [
            {
                "id": "T-SWARM-01",
                "pool": "mac-google",
                "title": "Mac Google test task 1",
                "exclusive_group": "group_alpha",
            },
            {
                "id": "T-SWARM-02",
                "pool": "mac-google",
                "title": "Mac Google test task 2",
                "exclusive_group": "group_alpha",
            },
            {
                "id": "T-SWARM-03",
                "pool": "windows-google",
                "title": "Windows Google task",
            },
        ]
    }
    bank_file.write_text(json.dumps(taskbank), encoding="utf-8")

    monkeypatch.setattr(local_swarm_claim, "ROOT", root)
    monkeypatch.setattr(local_swarm_claim, "BANK", bank_file)
    monkeypatch.setattr(local_swarm_claim, "STATE", state)
    monkeypatch.setattr(local_swarm_claim, "CLAIMS", state / "claims")
    monkeypatch.setattr(local_swarm_claim, "DONE", state / "done")
    monkeypatch.setattr(local_swarm_claim, "BLOCKED", state / "blocked")
    monkeypatch.setattr(local_swarm_claim, "LOCKS", state / "locks")
    monkeypatch.setattr(local_swarm_claim, "STOP", state / "STOP")

    return root, state


def test_swarm_claim_and_complete_lifecycle(mock_swarm_env):
    root, state = mock_swarm_env

    # 1. Initial claim
    code = local_swarm_claim.claim("mac-google")
    assert code == 0

    claim_dir = state / "claims" / "T-SWARM-01"
    assert claim_dir.exists()
    claim_meta = json.loads((claim_dir / "claim.json").read_text(encoding="utf-8"))
    token = claim_meta["token"]
    assert claim_meta["task_id"] == "T-SWARM-01"
    assert claim_meta["exclusive_group"] == "group_alpha"

    # Exclusive group lock held
    group_lock = state / "locks" / "group_alpha" / "owner.json"
    assert group_lock.exists()

    # Second claim for same pool blocked due to exclusive group
    code2 = local_swarm_claim.claim("mac-google")
    assert code2 == 2  # NO_TASK available because group_alpha is locked

    # 2. Complete task
    code_fin = local_swarm_claim.finish("complete", "T-SWARM-01", token, "Finished work")
    assert code_fin == 0

    assert not claim_dir.exists()
    assert not group_lock.exists()
    done_file = state / "done" / "T-SWARM-01.json"
    assert done_file.exists()
    done_data = json.loads(done_file.read_text(encoding="utf-8"))
    assert done_data["summary"] == "Finished work"

    # 3. Next claim for same pool succeeds now that lock is freed
    code3 = local_swarm_claim.claim("mac-google")
    assert code3 == 0
    claim_dir2 = state / "claims" / "T-SWARM-02"
    assert claim_dir2.exists()


def test_swarm_claim_stop_and_resume(mock_swarm_env):
    root, state = mock_swarm_env

    # Set emergency stop
    state.mkdir(parents=True, exist_ok=True)
    stop_file = state / "STOP"
    stop_file.write_text("emergency pause", encoding="utf-8")

    code = local_swarm_claim.claim("mac-google")
    assert code == 3  # STOPPED code

    # Remove stop
    stop_file.unlink()
    code2 = local_swarm_claim.claim("mac-google")
    assert code2 == 0


def test_swarm_release_unlocks(mock_swarm_env):
    root, state = mock_swarm_env

    code = local_swarm_claim.claim("mac-google")
    assert code == 0

    claim_dir = state / "claims" / "T-SWARM-01"
    token = json.loads((claim_dir / "claim.json").read_text(encoding="utf-8"))["token"]

    claim_meta = local_swarm_claim.readclaim("T-SWARM-01")
    local_swarm_claim.unlock(claim_meta)

    assert not claim_dir.exists()
    assert not (state / "locks" / "group_alpha").exists()


def test_swarm_status_reporting(mock_swarm_env, capsys):
    root, state = mock_swarm_env
    code = local_swarm_claim.status()
    assert code == 0
    out, err = capsys.readouterr()
    status_data = json.loads(out)
    assert "pools" in status_data
    assert "mac-google" in status_data["pools"]
    assert status_data["pools"]["mac-google"]["total"] == 2
    assert status_data["pools"]["windows-google"]["total"] == 1
