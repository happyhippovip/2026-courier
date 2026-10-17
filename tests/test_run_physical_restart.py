import subprocess
import sys

import pytest
from pathlib import Path
import json

import pytest; pytest.importorskip("fcntl")


def _write_run1(run1_dir: Path, sha: str = "abcd") -> None:
    run1_evidence = run1_dir / "evidence"
    run1_evidence.mkdir(parents=True)
    (run1_evidence / "run1_exit_code.txt").write_text("0")
    (run1_evidence / "run1_state_snapshot.json").write_text(json.dumps({
        "final_status": "SUCCESS",
        "payload": {},
        "candidate_sha": sha,
    }))


def _assert_no_success_record(evidence: Path, stdout: str) -> None:
    assert "Restart completed successfully" not in stdout
    assert "Resumed and completed B" not in stdout
    if not evidence.exists():
        return
    for path in evidence.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "Restart completed successfully" not in text
        assert "Resumed and completed B" not in text
        assert '"final_status": "SUCCESS"' not in text
        if path.name == "run2_exit_code.txt":
            assert text.strip() != "0"


def test_run_physical_restart_gate_pass_is_not_a_restart(tmp_path, capsys):
    import scripts.run_physical_restart as script

    run1_dir = tmp_path / "run1"
    _write_run1(run1_dir)
    run2_evidence = tmp_path / "run2_evidence"

    code = script.execute_run2("abcd", str(run1_dir), str(run2_evidence), 8081)

    assert code != 0
    _assert_no_success_record(run2_evidence, capsys.readouterr().out)


def _sleep_proc():
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_restart_success_requires_spawn_identity(tmp_path, capsys):
    import scripts.run_physical_restart as script

    run1_dir = tmp_path / "run1"
    _write_run1(run1_dir)
    evidence = tmp_path / "run2_evidence"
    proc = _sleep_proc()
    try:
        identity = script.capture_spawn_identity(proc)
        assert identity["pid"] == proc.pid
        code = script.execute_run2(
            "abcd", str(run1_dir), str(evidence), 8081, spawn_identity=identity,
        )
    finally:
        proc.kill()
        proc.wait(timeout=5)

    captured = capsys.readouterr().out
    assert code == 0
    assert "Restart completed successfully" in captured
    assert "Resumed and completed B" not in captured
    record = json.loads((evidence / "run2_restart_identity.json").read_text())
    assert record["pid"] == identity["pid"]
    assert record["create_time"] == identity["create_time"]
    assert record["candidate_sha"] == "abcd"
    assert (evidence / "run2_exit_code.txt").read_text().strip() == "0"
    assert not (evidence / "run2_state_snapshot.json").exists()
    combined = captured + (evidence / "run2_restart_identity.json").read_text()
    assert "Resumed and completed B" not in combined
    assert "automatic resume" not in combined.lower()


def test_restart_rejects_unverified_spawn_identity(tmp_path, capsys):
    import scripts.run_physical_restart as script

    run1_dir = tmp_path / "run1"
    _write_run1(run1_dir)
    evidence = tmp_path / "run2_evidence"
    proc = _sleep_proc()
    identity = script.capture_spawn_identity(proc)
    proc.kill()
    proc.wait(timeout=5)

    dead = script.execute_run2(
        "abcd", str(run1_dir), str(evidence), 8081, spawn_identity=identity,
    )
    dead_out = capsys.readouterr().out
    assert dead != 0
    _assert_no_success_record(evidence, dead_out)

    alive = _sleep_proc()
    try:
        live_identity = script.capture_spawn_identity(alive)
        live_identity["create_time"] = live_identity["create_time"] - 10
        mismatch = script.execute_run2(
            "abcd", str(run1_dir), str(evidence), 8081, spawn_identity=live_identity,
        )
    finally:
        alive.kill()
        alive.wait(timeout=5)
    assert mismatch != 0
    _assert_no_success_record(evidence, capsys.readouterr().out)


def test_run_physical_restart_run1_fail(tmp_path, monkeypatch):
    import scripts.run_physical_restart as script
    
    monkeypatch.setattr(script, "check_resources", lambda *args, **kwargs: True)
    monkeypatch.setattr(script, "check_port_free", lambda *args, **kwargs: True)
    
    run1_dir = tmp_path / "run1_fail"
    run1_evidence = run1_dir / "evidence"
    run1_evidence.mkdir(parents=True)
    (run1_evidence / "run1_exit_code.txt").write_text("1")
    (run1_evidence / "run1_state_snapshot.json").write_text(json.dumps({"final_status": "FAIL", "payload": {}, "candidate_sha": "abcd"}))
    
    run2_evidence = tmp_path / "run2_evidence_fail"
    
    with pytest.raises(RuntimeError, match="RUN 1 did not PASS cleanly"):
        script.execute_run2("abcd", str(run1_dir), str(run2_evidence), 8081)

