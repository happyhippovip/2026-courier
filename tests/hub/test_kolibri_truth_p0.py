"""P0 truth tests for courier_hub/kolibri_data.py and the hub card proof (negative tests).

K1: a done task reaches Kolibri as verifier evidence only when its card says
"verified" (resolution verified, courier_hub/model.py done_outcome) AND carries
the journaled RESULT_ACCEPTED proof. The event id is that journal event, never
derived from the task id. A human-confirmed or unlabelled completion, or a
verified card without a valid proof, is never verified.
K2: an unknown amount is never a number. Without a readable
registries/arbitrage_research.json (missing, corrupt, or without the field)
verified_actual_revenue carries no amount_eur at all, so nothing renders
0.00 EUR next to UNAVAILABLE.
"""
import sys
from pathlib import Path

import pytest

from courier_hub import model
from courier_hub.kolibri_data import UNAVAILABLE, build_snapshot, read_arbitrage_research, read_ledger

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controller"))
from ctrl_helpers import FakeClock, Verifiers, accept_all, make_controller, run_attempt, task_body  # noqa: E402

AT = "2026-10-19T10:00:00Z"
PROOF = {"event": "RESULT_ACCEPTED", "seq": 7, "result_id": "r1"}


def _view(outcome, proof=None):
    card = {"id": "task-1", "title": "Report", "pile": "done", "outcome": outcome,
            "last_change": {"what": "Checked", "at": "2026-10-19T09:59:00Z"}}
    if proof is not None:
        card["proof"] = proof
    return {"truth": "ok", "read_at": AT, "needs_you": [], "working": [], "done": [card],
            "counts": {"needs_you": 0, "working": 0, "done": 1}, "done_shown": 1}


def test_k1_verified_outcome_with_journal_proof_is_evidence():
    item = read_ledger(_view("verified", PROOF), AT)["items"][0]
    assert item.get("verified") is True
    assert item["event_id"] == "journal:7:RESULT_ACCEPTED"


@pytest.mark.parametrize("proof", [
    None,
    {},
    {"event": "RESULT_ACCEPTED", "seq": True, "result_id": "r1"},
    {"event": "RESULT_ACCEPTED", "seq": 0, "result_id": "r1"},
    {"event": "RESULT_ACCEPTED", "seq": "7", "result_id": "r1"},
    {"event": "RESULT_ACCEPTED", "seq": 7, "result_id": ""},
    {"event": "TASK_COMPLETE", "seq": 7, "result_id": "r1"},
    "journal:7",
])
def test_k1_verified_outcome_without_valid_proof_stays_unverified(proof):
    item = read_ledger(_view("verified", proof), AT)["items"][0]
    assert item.get("verified") is not True
    assert "event_id" not in item


def test_k1_human_confirmed_or_unlabelled_is_never_verified_even_with_a_proof():
    for outcome in ("human_confirmed", "completed", None):
        item = read_ledger(_view(outcome, PROOF), AT)["items"][0]
        assert item.get("verified") is not True
        assert "event_id" not in item


def _journal(tmp_path):
    ctl = make_controller(tmp_path / "home", clock=FakeClock(), verifier=Verifiers(probe=accept_all))
    _, created = ctl.create_task(task_body())
    return ctl, created["task_id"]


def test_k1_card_proof_comes_from_the_real_result_accepted_event(tmp_path):
    ctl, task_id = _journal(tmp_path)
    run_attempt(ctl)
    ctl.drain()
    task = ctl.journal.task(task_id)
    events = [e for e in ctl.events_after(0, limit=500) if e.task_id == task_id]
    accepted = [e for e in events if e.type.value == "RESULT_ACCEPTED"]
    assert len(accepted) == 1

    card = model.card(task, events)
    assert card["proof"] == {"event": "RESULT_ACCEPTED", "seq": accepted[0].seq, "result_id": "r1"}
    item = read_ledger(_view(card["outcome"], card["proof"]), AT)["items"][0]
    assert item["event_id"] == f"journal:{accepted[0].seq}:RESULT_ACCEPTED"


def test_k1_card_without_the_accepted_event_carries_no_proof(tmp_path):
    ctl, task_id = _journal(tmp_path)
    run_attempt(ctl)
    ctl.drain()
    task = ctl.journal.task(task_id)
    events = [e for e in ctl.events_after(0, limit=500)
              if e.task_id == task_id and e.type.value != "RESULT_ACCEPTED"]
    assert "proof" not in model.card(task, events)


def _no_amount(block):
    revenue = block["verified_actual_revenue"]
    assert "amount_eur" not in revenue
    assert revenue["status"] in (UNAVAILABLE, "UNKNOWN")


def test_read_arbitrage_research_refuses_a_symlink(tmp_path: Path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"title":"SECRET","verified_actual_revenue":{"amount_eur":1}}', encoding="utf-8")
    root = tmp_path / "root"
    (root / "registries").mkdir(parents=True)
    (root / "registries" / "arbitrage_research.json").symlink_to(outside)
    block = read_arbitrage_research(root, AT)
    assert block["available"] is False
    assert "SECRET" not in str(block)
    _no_amount(block)
    assert outside.read_text(encoding="utf-8").startswith('{"title":"SECRET"')

    linked = tmp_path / "linked-root"
    linked.symlink_to(root)
    (root / "registries" / "arbitrage_research.json").unlink()
    (root / "registries" / "arbitrage_research.json").write_text(
        '{"title":"SECRET","verified_actual_revenue":{"amount_eur":1}}',
        encoding="utf-8",
    )
    through = read_arbitrage_research(linked, AT)
    assert through["available"] is False
    assert "SECRET" not in str(through)
    _no_amount(through)

    live = read_arbitrage_research(root, AT)
    assert live["available"] is True
    assert live["title"] == "SECRET"
    assert live["verified_actual_revenue"]["amount_eur"] == 1


def test_k2_missing_arbitrage_file_has_no_amount(tmp_path: Path):
    block = read_arbitrage_research(tmp_path, AT)
    assert block["available"] is False
    assert block.get("simulation", {}) in ({}, None)
    assert "net_simulated_profit_eur" not in str(block)
    _no_amount(block)


def test_k2_corrupt_arbitrage_file_has_no_amount(tmp_path: Path):
    (tmp_path / "registries").mkdir()
    (tmp_path / "registries" / "arbitrage_research.json").write_text("{not json", encoding="utf-8")
    block = read_arbitrage_research(tmp_path, AT)
    assert block["available"] is False
    _no_amount(block)


def test_k2_file_without_revenue_field_has_no_amount(tmp_path: Path):
    (tmp_path / "registries").mkdir()
    (tmp_path / "registries" / "arbitrage_research.json").write_text("{}", encoding="utf-8")
    _no_amount(read_arbitrage_research(tmp_path, AT))


def test_k2_snapshot_fallback_has_no_amount(tmp_path: Path, monkeypatch):
    import courier_hub.kolibri_data as kd

    def boom(*a, **k):
        raise RuntimeError("reader failed")
    monkeypatch.setattr(kd, "read_arbitrage_research", boom)
    _no_amount(build_snapshot(None, root=tmp_path, observed_at=AT)["arbitrage_research"])
