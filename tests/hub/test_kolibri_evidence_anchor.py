"""Kolibri evidence anchor: the hub builds the badge tuple from sealed journal events only.

The Kolibri evidence badge (courier_hub/static/evidence_badge.mjs) turns green only for the
six-field tuple, resolution BYTE_LEVEL_GOLD_VERIFIED and a journal proof. These tests pin
where that tuple may come from: a verified completion of an adapter whose verifier checks
artifact bytes, its journaled RESULT_ACCEPTED and the RESULT_READY of the same dispatch.
"""
import sys
from pathlib import Path

import pytest

from courier_hub import model
from courier_hub.kolibri_data import read_ledger

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controller"))
from ctrl_helpers import SHA, FakeClock, Verifiers, accept_all, make_controller, run_attempt, task_body  # noqa: E402

AT = "2026-10-21T10:00:00Z"


def _done(tmp_path, adapter="synthetic"):
    ctl = make_controller(tmp_path / "home", clock=FakeClock(), verifier=Verifiers(**{adapter: accept_all}))
    _, created = ctl.create_task(task_body(adapter=adapter))
    run_attempt(ctl)
    ctl.drain()
    task_id = created["task_id"]
    events = [e for e in ctl.events_after(0, limit=500) if e.task_id == task_id]
    return ctl.journal.task(task_id), events


def _view(card):
    return {"truth": "ok", "read_at": AT, "needs_you": [], "working": [], "done": [card],
            "counts": {"needs_you": 0, "working": 0, "done": 1}, "done_shown": 1}


def test_anchor_tuple_comes_from_the_sealed_journal_events(tmp_path):
    task, events = _done(tmp_path)
    accepted = [e for e in events if e.type.value == "RESULT_ACCEPTED"][0]
    evidence = model.card(task, events)["evidence"]
    assert evidence == {
        "journal_entry_id": f"journal:{accepted.seq}:RESULT_ACCEPTED",
        "task_id": task.task_id,
        "attempt": accepted.attempt,
        "dispatch_id": accepted.dispatch_id,
        "accepted_result_id": "r1",
        "artifact_sha256": SHA,
        "resolution": "BYTE_LEVEL_GOLD_VERIFIED",
        "proof": {"event": "RESULT_ACCEPTED", "seq": accepted.seq, "result_id": "r1"},
    }


def test_anchor_reaches_kolibri_only_bound_to_the_same_proof(tmp_path):
    task, events = _done(tmp_path)
    item = read_ledger(_view(model.card(task, events)), AT)["items"][0]
    assert item["verified"] is True
    assert item["evidence"]["journal_entry_id"] == item["event_id"]
    assert item["evidence"]["task_id"] == item["id"]


def test_no_anchor_for_an_adapter_without_byte_level_verifier(tmp_path):
    task, events = _done(tmp_path, adapter="probe")
    card = model.card(task, events)
    assert "proof" in card and "evidence" not in card


def test_no_anchor_without_the_ready_event_or_with_two_artifacts(tmp_path):
    task, events = _done(tmp_path)
    no_ready = [e for e in events if e.type.value != "RESULT_READY"]
    assert model.acceptance_evidence(task, no_ready) is None
    ready = next(e for e in events if e.type.value == "RESULT_READY")
    two = ready.__class__(**{**ready.__dict__, "payload": {**ready.payload,
                             "artifacts": ready.payload["artifacts"] * 2}})
    assert model.acceptance_evidence(task, [two if e is ready else e for e in events]) is None


@pytest.mark.parametrize("patch", [
    {"task_id": "task-other"},
    {"journal_entry_id": "journal:999:RESULT_ACCEPTED"},
    {"accepted_result_id": "r-other"},
    {"attempt": 0},
    {"attempt": True},
    {"artifact_sha256": "ABC"},
    {"resolution": "verified"},
    {"dispatch_id": ""},
])
def test_read_ledger_drops_a_tuple_that_does_not_bind(tmp_path, patch):
    task, events = _done(tmp_path)
    card = model.card(task, events)
    card["evidence"] = {**card["evidence"], **patch}
    item = read_ledger(_view(card), AT)["items"][0]
    assert item["verified"] is True  # the journal proof alone still marks it verified
    assert "evidence" not in item


def test_no_evidence_without_the_journal_proof(tmp_path):
    task, events = _done(tmp_path)
    card = model.card(task, events)
    card.pop("proof")
    item = read_ledger(_view(card), AT)["items"][0]
    assert "verified" not in item and "evidence" not in item
