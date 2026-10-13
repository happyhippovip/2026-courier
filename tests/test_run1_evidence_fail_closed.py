"""RUN1 evidence is fail-closed. A missing log is not a pass."""
import os
import sqlite3

import pytest

from scripts.verify_run1_evidence import verify_run1_evidence


def _db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tasks (task_id TEXT, status TEXT)")
    conn.execute("INSERT INTO tasks (task_id, status) VALUES ('A', 'RECONCILED')")
    conn.commit()
    conn.close()


def _evidence(tmp_path, *, server=True, worker=True, verifier=True, db=True):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    if db:
        _db(evidence / "ledger_run1.db")
    if server:
        (evidence / "server_run1.log").write_text(
            "Claimed task A\nResult for task A\n", encoding="utf-8"
        )
    if worker:
        (evidence / "worker_run1.log").write_text("worker up\n", encoding="utf-8")
    if verifier:
        (evidence / "verifier_run1.log").write_text("verifier up\n", encoding="utf-8")
    return evidence


def _run(evidence):
    with pytest.raises(SystemExit) as caught:
        verify_run1_evidence(str(evidence))
    return caught.value.code


def test_missing_server_log_fails_closed(tmp_path, capsys):
    code = _run(_evidence(tmp_path, server=False))
    assert code == 1
    assert "server_run1.log is missing" in capsys.readouterr().out


def test_missing_worker_and_verifier_logs_fail_closed(tmp_path, capsys):
    code = _run(_evidence(tmp_path, worker=False, verifier=False))
    output = capsys.readouterr().out
    assert code == 1
    assert "worker_run1.log is missing" in output
    assert "verifier_run1.log is missing" in output


def test_unreadable_ledger_fails_closed(tmp_path, capsys):
    evidence = _evidence(tmp_path, db=False)
    (evidence / "ledger_run1.db").write_text("not a database\n", encoding="utf-8")
    code = _run(evidence)
    assert code == 1
    assert "unreadable" in capsys.readouterr().out


def test_complete_bundle_passes_twice_without_new_files(tmp_path, capsys):
    evidence = _evidence(tmp_path)
    before = sorted(os.listdir(evidence))
    assert _run(evidence) == 0
    first = capsys.readouterr().out
    assert "RUN_1 EVIDENCE VALID" in first
    assert _run(evidence) == 0
    assert "RUN_1 EVIDENCE VALID" in capsys.readouterr().out
    assert sorted(os.listdir(evidence)) == before


def test_double_claim_in_a_real_log_fails_closed(tmp_path, capsys):
    evidence = _evidence(tmp_path)
    (evidence / "server_run1.log").write_text(
        "Claimed task A\nClaimed task A\nResult for task A\n", encoding="utf-8"
    )
    code = _run(evidence)
    assert code == 1
    assert "claimed 2 times" in capsys.readouterr().out
