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


def test_bool_failure_count_is_not_one_attempt(tmp_path, monkeypatch):
    """True is not one failure. An undecidable count must not become attempt 2."""
    qp = load_qp(monkeypatch, tmp_path)

    def boom(path):
        raise ValueError("boom")

    monkeypatch.setattr(qp, "dispatch_intake", boom)
    pending = tmp_path / "intakes" / "pending"
    pending.mkdir(parents=True)
    (pending / "poison.json").write_text("{not json")
    (tmp_path / "intakes" / ".failure_counts.json").write_text(
        json.dumps({"poison.json": True}), encoding="utf-8")
    qp.process_queue()
    parked = tmp_path / "intakes" / "quarantine" / "poison.json"
    assert parked.exists(), qp._load_counts()
    assert not (pending / "poison.json").exists()
    (pending / "other.json").write_text("{not json")
    (tmp_path / "intakes" / ".failure_counts.json").write_text(
        json.dumps({"other.json": False}), encoding="utf-8")
    qp.process_queue()
    assert (tmp_path / "intakes" / "quarantine" / "other.json").exists()


def test_quarantine_does_not_follow_a_directory_symlink(tmp_path, monkeypatch):
    """A symlinked quarantine directory must not receive the parked intake."""
    qp = load_qp(monkeypatch, tmp_path)
    monkeypatch.setattr(qp, "dispatch_intake", lambda path: (_ for _ in ()).throw(ValueError("poison")))
    outside = tmp_path / "outside"
    outside.mkdir()
    intakes = tmp_path / "intakes"
    intakes.mkdir()
    (intakes / "quarantine").symlink_to(outside, target_is_directory=True)
    pending = intakes / "pending"
    pending.mkdir()
    (pending / "poison.json").write_text("{not json")
    for _ in range(qp.POISON_QUARANTINE_AFTER):
        qp.process_queue()
    names = sorted(path.name for path in outside.iterdir())
    assert names == [], names
    assert (pending / "poison.json").is_file()


def test_processed_does_not_follow_a_directory_symlink(tmp_path, monkeypatch):
    """A symlinked processed directory must not receive a finished intake."""
    qp = load_qp(monkeypatch, tmp_path)
    monkeypatch.setattr(qp, "dispatch_intake", lambda path: "task-ok")
    outside = tmp_path / "outside"
    outside.mkdir()
    intakes = tmp_path / "intakes"
    intakes.mkdir()
    (intakes / "processed").symlink_to(outside, target_is_directory=True)
    pending = intakes / "pending"
    pending.mkdir()
    write_valid(pending / "good.json")
    qp.process_queue()
    names = sorted(path.name for path in outside.iterdir())
    assert names == [], names
    assert (pending / "good.json").is_file()


def test_pending_symlink_is_not_dispatched(tmp_path, monkeypatch):
    """A symlinked pending directory must not be read or moved."""
    qp = load_qp(monkeypatch, tmp_path)
    calls = []

    def fake_dispatch(path):
        calls.append(path)
        raise ValueError("should not run")

    monkeypatch.setattr(qp, "dispatch_intake", fake_dispatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "foreign.json").write_text("{not json")
    intakes = tmp_path / "intakes"
    intakes.mkdir()
    (intakes / "pending").symlink_to(outside, target_is_directory=True)
    qp.process_queue()
    assert calls == [], calls
    assert (outside / "foreign.json").read_text() == "{not json"
    assert [path.name for path in outside.iterdir()] == ["foreign.json"]


def test_failure_count_symlink_is_not_four_attempts(tmp_path, monkeypatch):
    """A symlinked counts file must not contribute four prior failures."""
    qp = load_qp(monkeypatch, tmp_path)
    monkeypatch.setattr(qp, "dispatch_intake", lambda path: (_ for _ in ()).throw(ValueError("poison")))
    outside = tmp_path / "outside-counts.json"
    body = json.dumps({"poison.json": 4})
    outside.write_text(body, encoding="utf-8")
    intakes = tmp_path / "intakes"
    intakes.mkdir()
    (intakes / ".failure_counts.json").symlink_to(outside)
    pending = intakes / "pending"
    pending.mkdir()
    (pending / "poison.json").write_text("{not json")
    qp.process_queue()
    parked = intakes / "quarantine" / "poison.json"
    assert not parked.exists(), outside.read_text(encoding="utf-8")
    assert (pending / "poison.json").is_file()
    assert outside.read_text(encoding="utf-8") == body
