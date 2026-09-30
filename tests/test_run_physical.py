import pytest
from pathlib import Path
import json
import os

def test_run_physical_success(tmp_path, monkeypatch):
    import scripts.run_physical as script
    
    # Mock system checks
    monkeypatch.setattr(script, "check_resources", lambda *args, **kwargs: True)
    monkeypatch.setattr(script, "check_port_free", lambda *args, **kwargs: True)
    
    monkeypatch.setenv("no_proxy", "*")

    evidence_dir = tmp_path / "evidence"
    
    # Execute run1
    exit_code = script.execute_run("1234abcd", str(evidence_dir), 8081)
    
    assert exit_code == 0
    assert (evidence_dir / "run1_stdout.log").exists()
    exit_lines = (evidence_dir / "run1_exit_code.txt").read_text().strip().splitlines()
    assert exit_lines[0] == "0"
    assert exit_lines[1] == "SUCCESS"
    
    snapshot = json.loads((evidence_dir / "run1_state_snapshot.json").read_text())
    assert snapshot["final_status"] == "SUCCESS"
    assert snapshot["candidate_sha"] == "1234abcd"
    
    # Verify hash exists
    assert (evidence_dir / "run1_falsifiability_hash.txt").exists()


@pytest.mark.parametrize("status,expected", [
    ("SUCCESS", 0),
    ("BLOCKED", 1),
    ("FAILED_TERMINAL", 1),
    ("QUEUED", 1),
    ("UNKNOWN", 1),
])
def test_exit_code_for_status(status, expected):
    """P2: process exit is 0 iff the run reached SUCCESS (file + return share it)."""
    import scripts.run_physical as script

    assert script.exit_code_for_status(status) == expected


def _write_run1_bundle(run1_dir, exit_text, snapshot):
    evidence = Path(run1_dir) / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "run1_exit_code.txt").write_text(exit_text)
    (evidence / "run1_state_snapshot.json").write_text(json.dumps(snapshot))


def test_run2_gate_rejects_stale_sha(tmp_path):
    """P3: a RUN_1 bundle for another SHA must be refused (live 34b0a426 case)."""
    import scripts.run_physical_restart as restart

    run1_dir = tmp_path / "run1"
    _write_run1_bundle(run1_dir, "0\nSUCCESS\n", {
        "final_status": "SUCCESS",
        "candidate_sha": "34b0a4264bf763bc2a78f761ffba36e47706b2cf",
    })

    with pytest.raises(RuntimeError, match="candidate_sha mismatch"):
        restart.execute_run2("1234abcd", str(run1_dir), str(tmp_path / "evidence2"))


def test_run2_gate_rejects_nonzero_exit(tmp_path):
    """P3: a RUN_1 bundle with nonzero exit file must be refused."""
    import scripts.run_physical_restart as restart

    run1_dir = tmp_path / "run1"
    _write_run1_bundle(run1_dir, "1\nBLOCKED\n", {
        "final_status": "BLOCKED",
        "candidate_sha": "1234abcd",
    })

    with pytest.raises(RuntimeError, match="did not PASS cleanly"):
        restart.execute_run2("1234abcd", str(run1_dir), str(tmp_path / "evidence2"))


def test_run2_gate_rejects_empty_exit_file(tmp_path):
    """P3: an empty exit file is fail-closed, not a PASS."""
    import scripts.run_physical_restart as restart

    run1_dir = tmp_path / "run1"
    _write_run1_bundle(run1_dir, "", {
        "final_status": "SUCCESS",
        "candidate_sha": "1234abcd",
    })

    with pytest.raises(RuntimeError, match="exit code file empty"):
        restart.execute_run2("1234abcd", str(run1_dir), str(tmp_path / "evidence2"))


def test_run2_gate_accepts_matching_bundle(tmp_path):
    """P3: exit 0 + SUCCESS + matching SHA passes the gate (incl. legacy 1-line exit file)."""
    import scripts.run_physical_restart as restart

    for exit_text in ("0\nSUCCESS\n", "0\n"):
        run1_dir = tmp_path / f"run1_{len(exit_text)}"
        _write_run1_bundle(run1_dir, exit_text, {
            "final_status": "SUCCESS",
            "candidate_sha": "1234abcd",
        })
        evidence_dir = tmp_path / f"evidence2_{len(exit_text)}"

        assert restart.execute_run2("1234abcd", str(run1_dir), str(evidence_dir)) == 0
        snapshot = json.loads((evidence_dir / "run2_state_snapshot.json").read_text())
        assert snapshot["candidate_sha"] == "1234abcd"

