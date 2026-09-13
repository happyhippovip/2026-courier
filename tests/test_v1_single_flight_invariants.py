import pytest
from pathlib import Path
import json

def test_no_multiple_active_root_goals():
    goals_path = Path("events/founder-mode/goals.json")
    if not goals_path.exists():
        return
    
    with open(goals_path, "r") as f:
        goals = json.load(f)
        
    active_goals = [g for g in goals if g.get("status") == "ACTIVE"]
    assert len(active_goals) <= 1, "V1 INVARIANT BROKEN: Multiple active root goals found"

def test_no_live_state_resets_in_tests():
    # Scan tests directory for prohibited live-state reset patterns
    prohibited = [
        "rm events/task-envelopes/*",
        "rm -rf events/task-envelopes",
        "open('events/founder-mode/goals.json', 'w').write('[]')",
        "open('events/mission-queue/queue.json', 'w').write",
    ]
    
    for fpath in Path("tests").rglob("*.py"):
        if fpath.name == "test_v1_single_flight_invariants.py":
            continue
        content = fpath.read_text(encoding="utf-8")
        for p in prohibited:
            assert p not in content, f"V1 INVARIANT BROKEN: Destructive live state reset '{p}' found in {fpath}"

def test_single_flight_fail_closed():
    from scripts.single_flight import is_single_flight_locked
    # Temporarily corrupt goals.json to test fail-closed
    goals_path = Path("events/founder-mode/goals.json")
    if not goals_path.exists():
        return
    
    backup = goals_path.read_text(encoding="utf-8")
    try:
        goals_path.write_text("MALFORMED JSON {", encoding="utf-8")
        assert is_single_flight_locked(Path(".")), "V1 INVARIANT BROKEN: Single-flight guard failed open on corrupt state!"
    finally:
        goals_path.write_text(backup, encoding="utf-8")
