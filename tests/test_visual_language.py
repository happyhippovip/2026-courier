import re

from courier_runtime import continuity, surfaces, visual_language as vl


def _constants(module, names):
    return {getattr(module, n) for n in names}


def test_every_surface_state_has_exactly_one_colour():
    states = surfaces.BUSY | surfaces.REUSABLE | surfaces.DEAD
    assert states == set(vl.SURFACE_STATE)


def test_every_continuity_state_has_a_colour():
    workkey = _constants(continuity, ["OPEN", "CLAIMED", "DONE", "BLOCKED", "FAILED_FINAL"])
    session = continuity.LIVE | {continuity.RETIRED}
    assert workkey == set(vl.WORKKEY_STATE)
    assert session == set(vl.SESSION_STATE)


def test_admission_actions_match_decision_contract():
    src = open(surfaces.__file__, encoding="utf-8").read()
    listed = set(re.search(r"action: str\s+# ([A-Z_| ]+)", src).group(1).replace(" ", "").split("|"))
    assert listed == set(vl.ADMISSION)


def test_no_shadow_no_claim_unknown_is_never_green():
    for kind in vl.TABLES:
        assert vl.colour(kind, "SOMETHING_NEW") == vl.GREY
    assert vl.colour("surface", surfaces.TERMINAL_HOST_FAILED) == vl.RED
    assert vl.colour("workkey", continuity.DONE) == vl.GREEN
    assert vl.colour("workkey", continuity.BLOCKED) == vl.AMBER


def test_beam_only_hits_what_was_really_closed():
    reclaim = [{"surface_id": "a", "closed": True},
               {"surface_id": "b", "closed": False, "reasons": ["unsaved"]}]
    plan = dict(vl.beam_plan(reclaim, {"c": "STALE", "d": "REUSABLE", "e": "ORPHANED"}))
    assert plan == {"a": "red_beam", "b": "amber_hold", "c": "red_beam",
                    "d": "green_link", "e": "grey_mark"}


def test_hex_palette_complete():
    assert set(vl.HEX) == {vl.RED, vl.GREEN, vl.AMBER, vl.BLUE, vl.GREY}
