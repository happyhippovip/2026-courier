import re
import pytest

from courier_runtime import continuity as _c
from courier_runtime import surfaces as _s
from courier_runtime import visual_language as vl


class TestVisualLanguageExtended:
    """Rigorous edge-case verification of Courier visual language contracts."""

    def test_hex_code_syntax_and_uniqueness(self):
        # Hex colors must be valid #RRGGBB strings
        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for color_name, hex_val in vl.HEX.items():
            assert hex_pattern.match(hex_val), f"Invalid hex color format: {hex_val} for {color_name}"
        # All colors must have unique distinct hex codes
        assert len(set(vl.HEX.values())) == len(vl.HEX)

    def test_beam_plan_empty_inputs(self):
        # Empty reclaim and None reconcile
        assert vl.beam_plan() == []
        assert vl.beam_plan(reclaim_results=[]) == []
        assert vl.beam_plan(reclaim_results=[], reconcile_result=None) == []
        assert vl.beam_plan(reclaim_results=[], reconcile_result={}) == []

    def test_beam_plan_closed_flag_strictness(self):
        # Only closed=True gets red_beam; False, None, or absent key must get amber_hold
        reclaims = [
            {"surface_id": "s1", "closed": True},
            {"surface_id": "s2", "closed": False},
            {"surface_id": "s3", "closed": None},
            {"surface_id": "s4"},  # key omitted
        ]
        plan = vl.beam_plan(reclaim_results=reclaims)
        expected = [
            ("s1", "red_beam"),
            ("s2", "amber_hold"),
            ("s3", "amber_hold"),
            ("s4", "amber_hold"),
        ]
        assert plan == expected

    def test_beam_plan_reconcile_sorting_and_all_classifications(self):
        # Reconcile results must be sorted alphabetically by surface_id
        reconcile = {
            "surf_z": "COMPLETED",   # GREEN -> green_link
            "surf_a": "REUSABLE",    # GREEN -> green_link
            "surf_m": "STILL_ALIVE", # BLUE  -> green_link
            "surf_k": "STALE",       # RED   -> red_beam
            "surf_b": "ORPHANED",    # GREY  -> grey_mark
        }
        plan = vl.beam_plan(reconcile_result=reconcile)
        expected_sids = ["surf_a", "surf_b", "surf_k", "surf_m", "surf_z"]
        assert [sid for sid, _ in plan] == expected_sids

        plan_dict = dict(plan)
        assert plan_dict["surf_a"] == "green_link"
        assert plan_dict["surf_b"] == "grey_mark"
        assert plan_dict["surf_k"] == "red_beam"
        assert plan_dict["surf_m"] == "green_link"
        assert plan_dict["surf_z"] == "green_link"

    def test_beam_plan_combined_execution_order(self):
        # Reclaim events precede reconcile events in animation sequence
        reclaims = [{"surface_id": "r1", "closed": True}]
        reconcile = {"c1": "REUSABLE"}
        plan = vl.beam_plan(reclaim_results=reclaims, reconcile_result=reconcile)
        assert plan == [("r1", "red_beam"), ("c1", "green_link")]

    def test_admission_decision_colors(self):
        # Verified green states (safe reuse/coalesce)
        assert vl.colour("admission", "REUSE") == vl.GREEN
        assert vl.colour("admission", "COALESCED") == vl.GREEN

        # Active working states
        assert vl.colour("admission", "OPEN") == vl.BLUE
        assert vl.colour("admission", "HEADLESS") == vl.BLUE

        # Waiting states
        assert vl.colour("admission", "QUEUED") == vl.AMBER

        # Unrecognized admission
        assert vl.colour("admission", "UNAUTHORIZED") == vl.GREY

    def test_reconcile_classification_colors(self):
        assert vl.colour("reconcile", "COMPLETED") == vl.GREEN
        assert vl.colour("reconcile", "REUSABLE") == vl.GREEN
        assert vl.colour("reconcile", "STILL_ALIVE") == vl.BLUE
        assert vl.colour("reconcile", "STALE") == vl.RED
        assert vl.colour("reconcile", "ORPHANED") == vl.GREY
        assert vl.colour("reconcile", "UNKNOWN_CRASH") == vl.GREY

    def test_all_session_states_mapped_correctly(self):
        assert vl.colour("session", _c.WORKING) == vl.BLUE
        assert vl.colour("session", _c.IDLE) == vl.GREEN
        assert vl.colour("session", _c.WAKE_PENDING) == vl.AMBER
        assert vl.colour("session", _c.WAITING_FOR_USER) == vl.AMBER
        assert vl.colour("session", _c.RECOVERING) == vl.AMBER
        assert vl.colour("session", _c.RETIRED) == vl.GREY
