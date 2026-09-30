"""Queue crash-consistency: dispatched-but-not-moved must recover without re-dispatch (Wave 4 Z3)."""
import importlib.util
import json
import logging
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def qp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "queue_processor_crash_under_test",
        ROOT / "scripts" / "queue_processor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []
    monkeypatch.setattr(mod, "dispatch_intake", lambda p: calls.append(p))
    mod._dispatch_calls = calls
    return mod


def write_pending(name="in-1.json"):
    (Path("intakes/pending") ).mkdir(parents=True, exist_ok=True)
    p = Path("intakes/pending") / name
    p.write_text(json.dumps({"customer_reference": "c"}))
    return p


def test_success_moves_file_and_leaves_no_marker(qp):
    write_pending()
    qp.process_queue()
    assert (Path("intakes/processed") / "in-1.json").is_file()
    assert list(Path("intakes").rglob("*.dispatched")) == []
    assert qp._dispatch_calls != []


def test_crash_after_dispatch_recovers_without_redispatch(qp, monkeypatch):
    write_pending()
    real_move = shutil.move
    def crashing_move(*a, **k):
        raise OSError("crash before move")
    monkeypatch.setattr(shutil, "move", crashing_move)
    qp.process_queue()  # move failure is caught; file stays in processing/
    assert len(qp._dispatch_calls) == 1
    assert (Path("intakes/processing") / "in-1.json").is_file()
    monkeypatch.setattr(shutil, "move", real_move)
    qp.process_queue()
    assert (Path("intakes/processed") / "in-1.json").is_file()
    assert len(qp._dispatch_calls) == 1, "must not dispatch twice"
    assert list(Path("intakes").rglob("*.dispatched")) == []


def test_failed_dispatch_writes_no_marker(qp):
    write_pending()
    qp.dispatch_intake = lambda p: (_ for _ in ()).throw(SystemExit(3))
    qp.process_queue()
    assert (Path("intakes/processing") / "in-1.json").is_file()
    assert list(Path("intakes").rglob("*.dispatched")) == []


def test_missing_gh_cli_stops_batch_and_returns_file_to_pending(qp):
    write_pending("in-1.json")
    write_pending("in-2.json")
    calls = []
    def no_gh(path):
        calls.append(path)
        raise SystemExit(2)
    qp.dispatch_intake = no_gh
    qp.process_queue()
    # Batch stopped at the environmental failure: second file never attempted,
    # first file returned to pending (not triaged as poison).
    assert len(calls) == 1
    assert (Path("intakes/pending") / "in-1.json").is_file()
    assert (Path("intakes/pending") / "in-2.json").is_file()
    assert list(Path("intakes/processing").glob("*.json")) == []
    assert list(Path("intakes").rglob("*.dispatched")) == []


def test_orphan_marker_without_sibling_is_cleaned(qp):
    Path("intakes/processing").mkdir(parents=True, exist_ok=True)
    (Path("intakes/processing") / "gone.json.dispatched").write_text("ok")
    qp.process_queue()
    assert list(Path("intakes").rglob("*.dispatched")) == []
    assert qp._dispatch_calls == []


def test_stale_processing_backlog_is_logged(qp, caplog):
    Path("intakes/processing").mkdir(parents=True, exist_ok=True)
    (Path("intakes/processing") / "stuck.json").write_text("{}")
    with caplog.at_level(logging.INFO, logger=qp.logger.name):
        qp.process_queue()
    assert "stuck.json" in caplog.text or "backlog" in caplog.text
