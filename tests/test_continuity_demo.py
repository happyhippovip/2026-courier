"""The one-command continuity demo runs end to end and its receipt is checkable.

One real controller and worker run once (module fixture, about 30 s). The
tamper cases work on copies of that evidence dir: an edited receipt, an edited
ledger and an edited journal must each make ``verify`` fail.

Synthetic adapter only: this is the contract proof, not a provider run.
Lives outside tests/golden, so the golden skip does not apply.
"""

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "continuity_demo.py"


def _cli(*args, timeout=300):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(REPO),
                          capture_output=True, text=True, timeout=timeout)


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    out = tmp_path_factory.mktemp("continuity") / "run"
    proc = _cli("run", "--out", str(out))
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    return out


def _copy(evidence, tmp_path):
    dest = tmp_path / "copy"
    shutil.copytree(evidence, dest)
    return dest


def test_run_writes_a_passing_receipt(evidence):
    receipt = json.loads((evidence / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["verdict"] == "PASS" and receipt["fails"] == []
    ev = receipt["evidence"]
    assert ev["tasks_created_total"] == 2
    assert ev["journal"]["chain_ok"] is True
    assert receipt["observed"]["worker_runs"] == 2
    assert receipt["observed"]["hard_kills"] == 1
    assert receipt["observed"]["replay_noop_after_done"] is True
    for name in ("A", "B"):
        m = ev["missions"][name]
        assert (m["tasks_created"], m["result_accepted"], m["task_complete"], m["ledger_final"]) == (1, 1, 1, 1)
        assert m["bridge_status"] == "FINAL_DONE" and m["final_bound_to_task"] and m["artifact_present"]
    assert ev["missions"]["A"]["task_id"] != ev["missions"]["B"]["task_id"]
    steps = [s["step"] for s in receipt["observed"]["timeline"]]
    kill = next(i for i, s in enumerate(steps) if "KILLED HARD" in s)
    assert any("A COMPLETE" in s for s in steps[:kill])
    assert any("FINAL_DONE" in s for s in steps[kill:])
    md = (evidence / "receipt.md").read_text(encoding="utf-8")
    assert "PASS" in md and receipt["receipt_sha256"] in md


def test_no_token_in_receipt_or_logs(evidence):
    token = (evidence / "home" / "run" / "controller.token").read_text(encoding="utf-8").strip()
    assert token
    for path in [evidence / "receipt.json", evidence / "receipt.md", *(evidence / "logs").iterdir()]:
        assert token not in path.read_text(encoding="utf-8", errors="replace"), path


def test_verify_passes_on_untouched_evidence(evidence):
    proc = _cli("verify", str(evidence), timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.startswith("VERIFY PASS")


def test_verify_fails_on_edited_receipt(evidence, tmp_path):
    copy = _copy(evidence, tmp_path)
    receipt = json.loads((copy / "receipt.json").read_text(encoding="utf-8"))
    receipt["evidence"]["tasks_created_total"] = 3
    (copy / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    proc = _cli("verify", str(copy), timeout=60)
    assert proc.returncode == 1 and "digest mismatch" in proc.stdout, proc.stdout


def test_verify_fails_on_edited_ledger(evidence, tmp_path):
    copy = _copy(evidence, tmp_path)
    ledger = copy / "home" / "coordination_ledger.jsonl"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace("goal_id=", "goal_id=x", 1), encoding="utf-8")
    proc = _cli("verify", str(copy), timeout=60)
    assert proc.returncode == 1 and "VERIFY FAIL" in proc.stdout, proc.stdout


def test_verify_fails_on_edited_journal(evidence, tmp_path):
    copy = _copy(evidence, tmp_path)
    db = copy / "home" / "courier.db"
    with sqlite3.connect(str(db)) as conn:
        conn.execute("DROP TRIGGER IF EXISTS events_no_update")
        conn.execute("UPDATE events SET ts_utc = '2000-01-01T00:00:00Z' WHERE seq = 1")
    proc = _cli("verify", str(copy), timeout=60)
    assert proc.returncode == 1, proc.stdout
    assert "hash chain broken" in proc.stdout or "differs" in proc.stdout, proc.stdout


def test_run_refuses_a_non_empty_out_dir(tmp_path):
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    proc = _cli("run", "--out", str(tmp_path), timeout=60)
    assert proc.returncode == 2
    assert (tmp_path / "keep.txt").read_text(encoding="utf-8") == "x"
