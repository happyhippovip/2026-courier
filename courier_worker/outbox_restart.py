"""Gate G4: outbox restart and cleanup without replay.

Ensures that restart resumes open entries exactly once and never replays
a confirmed effect. Cleanup only removes entries confirmed by journal proof.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Set


class OutboxRestartError(Exception):
    """Raised when an outbox entry is corrupt or restart cannot proceed safely."""
    pass


def record_confirmation(home: Path | str, effect_key: str, dispatch_id: str) -> None:
    """Record confirmation of an effect in the run journal."""
    home_path = Path(home)
    run_dir = home_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    journal = run_dir / "effect-journal.jsonl"
    entry = {
        "effect_key": effect_key,
        "dispatch_id": dispatch_id,
        "timestamp": time.time(),
        "status": "CONFIRMED",
    }
    with journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _load_confirmed_keys(home: Path) -> Set[str]:
    """Load confirmed effect keys and dispatch IDs from the journal."""
    journal = home / "run" / "effect-journal.jsonl"
    if not journal.is_file():
        return set()
    confirmed = set()
    for line in journal.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if "effect_key" in data and data["effect_key"]:
                confirmed.add(data["effect_key"])
            if "dispatch_id" in data and data["dispatch_id"]:
                confirmed.add(data["dispatch_id"])
        except json.JSONDecodeError:
            continue
    return confirmed


def resume_outbox(
    home: Path | str,
    execute_callback: Callable[[Dict[str, Any]], Any],
) -> Dict[str, List[str]]:
    """Resume pending outbox entries without replay.

    Returns a report with 'continued' and 'skipped' dispatch IDs.
    """
    home_path = Path(home)
    outbox = home_path / "outbox"
    if not outbox.is_dir():
        return {"continued": [], "skipped": []}

    # First pass: parse all outbox entries to detect corrupt files immediately (fail-closed)
    entries: List[tuple[Path, Dict[str, Any]]] = []
    for p in sorted(outbox.glob("*.json")):
        raw = p.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise OutboxRestartError(f"corrupt outbox entry (not a dict): {p.name}")
        except Exception as exc:
            raise OutboxRestartError(f"corrupt outbox entry: {p.name}") from exc
        entries.append((p, data))

    confirmed_keys = _load_confirmed_keys(home_path)
    seen_in_pass: Set[str] = set()

    continued: List[str] = []
    skipped: List[str] = []

    for p, entry in entries:
        effect_key = entry.get("effect_key")
        dispatch_id = entry.get("dispatch_id", p.stem)

        # Skip if already confirmed in journal or seen earlier in this pass
        is_confirmed = (
            (effect_key is not None and effect_key in confirmed_keys)
            or dispatch_id in confirmed_keys
        )
        is_duplicate = (effect_key is not None and effect_key in seen_in_pass)

        if is_confirmed or is_duplicate:
            skipped.append(dispatch_id)
            continue

        if effect_key is not None:
            seen_in_pass.add(effect_key)

        # Execute effect
        execute_callback(entry)

        # Record confirmation only on successful callback completion
        record_confirmation(home_path, effect_key or "", dispatch_id)
        if effect_key is not None:
            confirmed_keys.add(effect_key)
        confirmed_keys.add(dispatch_id)
        continued.append(dispatch_id)

    return {"continued": continued, "skipped": skipped}


def cleanup_confirmed(home: Path | str) -> List[str]:
    """Remove only outbox entries that have verified journal confirmation."""
    home_path = Path(home)
    outbox = home_path / "outbox"
    if not outbox.is_dir():
        return []

    # Parse all outbox entries to detect corrupt files fail-closed
    entries: List[tuple[Path, Dict[str, Any]]] = []
    for p in sorted(outbox.glob("*.json")):
        raw = p.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise OutboxRestartError(f"corrupt outbox entry (not a dict): {p.name}")
        except Exception as exc:
            raise OutboxRestartError(f"corrupt outbox entry: {p.name}") from exc
        entries.append((p, data))

    confirmed_keys = _load_confirmed_keys(home_path)
    removed: List[str] = []

    for p, entry in entries:
        effect_key = entry.get("effect_key")
        dispatch_id = entry.get("dispatch_id", p.stem)

        is_confirmed = (
            (effect_key is not None and effect_key in confirmed_keys)
            or dispatch_id in confirmed_keys
        )
        if is_confirmed:
            p.unlink()
            removed.append(dispatch_id)

    return removed
