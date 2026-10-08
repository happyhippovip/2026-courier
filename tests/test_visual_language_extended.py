import pytest
from courier_runtime import visual_language as vl
from courier_runtime import continuity, surfaces


def test_beam_plan_empty_and_defaults():
    assert vl.beam_plan() == []
    assert vl.beam_plan(reclaim_results=[]) == []
    assert vl.beam_plan(reconcile_result={}) == []


def test_beam_plan_ordering_and_mapping():
    reclaim = [
        {"surface_id": "surf-closed", "closed": True},
        {"surface_id": "surf-unclosed", "closed": False},
        {"surface_id": "surf-missing-key"},
    ]
    reconcile = {
        "z-surf": "COMPLETED",
        "a-surf": "STILL_ALIVE",
        "m-surf": "STALE",
    }
    plan = vl.beam_plan(reclaim, reconcile)

    # Reclaim items appear first in order of reclaim list
    assert plan[0] == ("surf-closed", "red_beam")
    assert plan[1] == ("surf-unclosed", "amber_hold")
    assert plan[2] == ("surf-missing-key", "amber_hold")

    # Reconcile items appear sorted alphabetically by surface_id
    assert plan[3] == ("a-surf", "green_link")
    assert plan[4] == ("m-surf", "red_beam")
    assert plan[5] == ("z-surf", "green_link")


def test_admission_and_reconcile_colours():
    assert vl.colour("admission", "REUSE") == vl.GREEN
    assert vl.colour("admission", "COALESCED") == vl.GREEN
    assert vl.colour("admission", "HEADLESS") == vl.BLUE
    assert vl.colour("admission", "OPEN") == vl.BLUE
    assert vl.colour("admission", "QUEUED") == vl.AMBER

    assert vl.colour("reconcile", "COMPLETED") == vl.GREEN
    assert vl.colour("reconcile", "REUSABLE") == vl.GREEN
    assert vl.colour("reconcile", "STILL_ALIVE") == vl.BLUE
    assert vl.colour("reconcile", "STALE") == vl.RED
    assert vl.colour("reconcile", "ORPHANED") == vl.GREY


def test_hex_codes_format():
    for name, hex_val in vl.HEX.items():
        assert hex_val.startswith("#")
        assert len(hex_val) == 7
        # Valid hex digits
        int(hex_val[1:], 16)
