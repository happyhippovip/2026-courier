"""Status snapshot for one Home: compact, read-only, deterministic, offline."""

import json
import socket

import pytest

from courier_core.status_snapshot import (
    SNAPSHOT_SCHEMA,
    SnapshotRefused,
    build_snapshot,
)

NOW = "2026-10-08T16:00:00Z"


def _card(pile, at="", outcome=None):
    card = {"id": f"{pile}-1", "pile": pile, "last_change": {"at": at} if at else None}
    if outcome is not None:
        card["outcome"] = outcome
    return card


def _home():
    return {
        "needs_you": [_card("needs_you", "2026-10-08T10:00:00Z")],
        "working": [_card("working", "2026-10-08T12:00:00Z")],
        "done": [_card("done", "2026-10-08T11:00:00Z", "verified"),
                 _card("done", "2026-10-08T09:00:00Z", "stopped")],
        "counts": {"needs_you": 1, "working": 1, "done": 2},
        "done_shown": 2,
    }


def test_builds_compact_snapshot_shape():
    snap = build_snapshot(_home(), now=NOW)
    assert snap["schema"] == SNAPSHOT_SCHEMA
    assert snap["generated_at"] == NOW
    assert snap["totals"] == {"needs_you": 1, "working": 1, "done": 2}
    assert snap["done_shown"] == 2
    assert snap["done_hidden"] == 0
    assert snap["needs_attention"] is True


def test_outcomes_tallied_and_sorted_with_oldest_and_newest():
    snap = build_snapshot(_home(), now=NOW)
    assert snap["outcomes"] == {"stopped": 1, "verified": 1}
    assert list(snap["outcomes"]) == ["stopped", "verified"]
    assert snap["oldest_needs_you_at"] == "2026-10-08T10:00:00Z"
    assert snap["newest_change_at"] == "2026-10-08T12:00:00Z"


def test_done_hidden_counts_trimmed_cards():
    home = _home()
    home["counts"] = {"needs_you": 0, "working": 0, "done": 5}
    home["done_shown"] = 2
    home["needs_you"] = []
    snap = build_snapshot(home, now=NOW)
    assert snap["done_hidden"] == 3
    assert snap["needs_attention"] is False
    assert snap["oldest_needs_you_at"] is None


def test_malformed_home_refused_fail_closed():
    with pytest.raises(SnapshotRefused):
        build_snapshot([], now=NOW)
    with pytest.raises(SnapshotRefused):
        build_snapshot({"working": [], "done": [], "counts": {}, "done_shown": 0}, now=NOW)
    with pytest.raises(SnapshotRefused):
        build_snapshot(_home(), now="yesterday")
    with pytest.raises(SnapshotRefused):
        build_snapshot(_home(), now="")


def test_no_network_calls_even_with_socket_blocked(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    snap = build_snapshot(_home(), now=NOW)
    assert snap["schema"] == SNAPSHOT_SCHEMA


def test_snapshot_is_json_stable_and_deterministic():
    first = json.dumps(build_snapshot(_home(), now=NOW), sort_keys=True)
    second = json.dumps(build_snapshot(_home(), now=NOW), sort_keys=True)
    assert first == second
    assert json.loads(first)["totals"]["done"] == 2
