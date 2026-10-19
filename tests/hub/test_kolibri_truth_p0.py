"""P0 truth tests for courier_hub/kolibri_data.py (negative tests, V101).

K1: a done task whose outcome is "verified" (controller verifier accepted the
result, courier_hub/model.py done_outcome) must reach Kolibri as verifier
evidence with a real event id. A human-confirmed or unlabelled completion
must never become verified.
K2: without registries/arbitrage_research.json the arbitrage block must be
unavailable, not a set of fixed numbers marked available.
"""
from pathlib import Path

from courier_hub.kolibri_data import UNAVAILABLE, read_arbitrage_research, read_ledger

AT = "2026-10-19T10:00:00Z"


def _view(outcome):
    card = {"id": "task-1", "title": "Report", "pile": "done", "outcome": outcome,
            "last_change": {"what": "Checked", "at": "2026-10-19T09:59:00Z"}}
    return {"truth": "ok", "read_at": AT, "needs_you": [], "working": [], "done": [card],
            "counts": {"needs_you": 0, "working": 0, "done": 1}, "done_shown": 1}


def test_k1_verified_outcome_reaches_kolibri_as_evidence():
    item = read_ledger(_view("verified"), AT)["items"][0]
    assert item.get("verified") is True
    assert item.get("event_id") and item["event_id"] != "evt:unknown:0"


def test_k1_human_confirmed_or_unlabelled_is_never_verified():
    for outcome in ("human_confirmed", "completed", None):
        item = read_ledger(_view(outcome), AT)["items"][0]
        assert item.get("verified") is not True


def test_k2_missing_arbitrage_file_is_unavailable(tmp_path: Path):
    block = read_arbitrage_research(tmp_path, AT)
    assert block["available"] is False
    assert block.get("simulation", {}) in ({}, None)
    assert "net_simulated_profit_eur" not in str(block)
