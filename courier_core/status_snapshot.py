"""Read-only status snapshot for one Home (lane L5).

Builds a compact, deterministic, JSON-ready snapshot from an already-built
``courier_hub.model.home()`` view. This module never imports the hub, never
touches the network or credentials, and performs no I/O: the caller passes
the home mapping in, and gets pure data out. Anything that is not a
home-shaped mapping is refused fail-closed instead of being guessed at.
"""

from __future__ import annotations

from typing import Any, Mapping

SNAPSHOT_SCHEMA = "home-status-snapshot/1"
_PILES = ("needs_you", "working", "done")
_TIME = frozenset("0123456789-T:Z")


class SnapshotRefused(ValueError):
    """The builder declined: the input is not a home-shaped mapping."""


def _at(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _changes(cards: list) -> list[str]:
    stamps = []
    for card in cards:
        if not isinstance(card, Mapping):
            raise SnapshotRefused("BAD_CARD")
        stamp = _at((card.get("last_change") or {}).get("at") if isinstance(
            card.get("last_change"), Mapping) else "")
        if stamp:
            stamps.append(stamp)
    return sorted(stamps)


def build_snapshot(home: Mapping[str, Any], *, now: str) -> dict:
    """Summarize one Home view into a status snapshot.

    ``home`` is a ``courier_hub.model.home()`` result: ``needs_you``,
    ``working`` and ``done`` card lists, a ``counts`` mapping, and
    ``done_shown``. ``now`` stamps the snapshot and must be a UTC
    ``YYYY-MM-DDTHH:MM:SSZ`` string. Card ``outcome`` values on done cards
    are tallied verbatim and sorted, so new outcomes never break the shape.
    """
    if not isinstance(home, Mapping):
        raise SnapshotRefused("BAD_HOME")
    piles = {}
    for pile in _PILES:
        cards = home.get(pile)
        if not isinstance(cards, list):
            raise SnapshotRefused(f"BAD_PILE:{pile}")
        piles[pile] = cards
    counts = home.get("counts")
    if not isinstance(counts, Mapping) or any(
            not isinstance(counts.get(pile), int) for pile in _PILES):
        raise SnapshotRefused("BAD_COUNTS")
    done_shown = home.get("done_shown")
    if isinstance(done_shown, bool) or not isinstance(done_shown, int) or done_shown < 0:
        raise SnapshotRefused("BAD_DONE_SHOWN")
    if not isinstance(now, str) or not now or any(char not in _TIME for char in now):
        raise SnapshotRefused("BAD_NOW")
    outcomes: dict[str, int] = {}
    for card in piles["done"]:
        if not isinstance(card, Mapping):
            raise SnapshotRefused("BAD_CARD")
        outcome = card.get("outcome", "unknown")
        outcome = outcome if isinstance(outcome, str) and outcome else "unknown"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    needs_stamps = _changes(piles["needs_you"])
    all_stamps = sorted(needs_stamps + _changes(piles["working"]) + _changes(piles["done"]))
    return {
        "schema": SNAPSHOT_SCHEMA,
        "generated_at": now,
        "totals": {pile: counts[pile] for pile in _PILES},
        "done_shown": done_shown,
        "done_hidden": max(0, counts["done"] - done_shown),
        "outcomes": {key: outcomes[key] for key in sorted(outcomes)},
        "oldest_needs_you_at": needs_stamps[0] if needs_stamps else None,
        "newest_change_at": all_stamps[-1] if all_stamps else None,
        "needs_attention": bool(piles["needs_you"]),
    }
