"""Poison-intake quarantine: bounded retries, then parked with a reason.

Proves: a deterministically-poison intake (invalid JSON) is quarantined
after POISON_QUARANTINE_AFTER consecutive failures instead of retried
forever, the rest of the batch keeps advancing, and a later success
clears the failure count. No subprocesses, no network: failures happen
before any external call.
"""
import importlib.util
import json
from pathlib import Path

QP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "queue_processor.py"


def load_qp(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(QP_PATH.parent))  # intake_dispatcher import
    spec = importlib.util.spec_from_file_location("queue_processor_poison", QP_PATH)
    qp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qp)
    return qp


def write_valid(path):
    path.write_text(json.dumps({"customer_reference": "r", "target_owner": "o",
                                "target_repo": "r", "target_sha": "s"}))


def test_poison_quarantined_after_bound_and_batch_advances(tmp_path, monkeypatch):
    qp = load_qp(monkeypatch, tmp_path)
    calls = []

    def fake_dispatch(path):
        calls.append(path)
        if "poison" in path:
            raise ValueError("deterministic poison")
        return "task-ok"

    monkeypatch.setattr(qp, "dispatch_intake", fake_dispatch)
    pending = tmp_path / "intakes" / "pending"
    pending.mkdir(parents=True)
    (pending / "poison.json").write_text("{not json")
    write_valid(pending / "good.json")
    for _ in range(qp.POISON_QUARANTINE_AFTER):
        qp.process_queue()
    assert (tmp_path / "intakes" / "processed" / "good.json").exists()
    assert (tmp_path / "intakes" / "quarantine" / "poison.json").exists()
    reason = json.loads((tmp_path / "intakes" / "quarantine"
                         / "poison.json.reason.json").read_text())
    assert reason["file"] == "poison.json"
    assert reason["failures"] >= qp.POISON_QUARANTINE_AFTER
    assert reason["last_error"]
    before = len(calls)
    qp.process_queue()
    qp.process_queue()
    assert len(calls) == before  # parked file is never attempted again


def test_success_clears_failure_count(tmp_path, monkeypatch):
    qp = load_qp(monkeypatch, tmp_path)

    def boom(path):
        raise ValueError("boom")

    monkeypatch.setattr(qp, "dispatch_intake", boom)
    pending = tmp_path / "intakes" / "pending"
    pending.mkdir(parents=True)
    (pending / "flaky.json").write_text("{not json")
    qp.process_queue()
    qp.process_queue()
    assert qp._load_counts().get("flaky.json") == 2
    write_valid(pending / "flaky.json")
    monkeypatch.setattr(qp, "dispatch_intake", lambda path: "task-ok")
    qp.process_queue()
    assert (tmp_path / "intakes" / "processed" / "flaky.json").exists()
    assert "flaky.json" not in qp._load_counts()
