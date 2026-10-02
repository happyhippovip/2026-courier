"""Readiness is derived, never typed: these tests pin the frozen progress law."""
import copy
import datetime
import json

import pytest

from scripts import readiness
from scripts.readiness import (compute, customer_tree, customer_view, dev_tree, dev_view, effective_state,
                               load_registry, summarize, validate)

TODAY = datetime.date(2026, 10, 2)
REQUIRED_FIELDS = ("id", "stage", "substage", "customer_label", "required_evidence_level", "state",
                   "evidence_ref", "evidence_sha", "owner", "blocker", "next_action", "freshness")


def crit(cid, stage="A", state="NOT_STARTED", **over):
    item = {"id": cid, "stage": stage, "substage": "Part", "title": f"title {cid}", "customer_label": f"label {cid}",
            "required_evidence_level": "E3", "state": state, "evidence_level": "E0", "evidence_ref": None,
            "evidence_sha": None, "owner": "lane", "blocker": None, "next_action": "do it",
            "freshness": {"verified_version": None, "verified_at": None, "max_age_days": None, "watch_paths": []}}
    if state == "VERIFIED":
        item.update(evidence_level="E3", evidence_ref="ci/run/1", evidence_sha="abc123",
                    freshness={"verified_version": "v1", "verified_at": "2026-10-01", "max_age_days": None,
                               "watch_paths": ["src/**"]})
    if state == "BLOCKED":
        item["blocker"] = "named blocker"
    item.update(over)
    return item


def reg(*items, **top):
    base = {"project": "P", "current_version": "v1",
            "evidence_levels": ["E0", "E1", "E2", "E3", "E4", "E5", "E6"], "freshness_days": {"E3": 30, "E4": 7},
            "stages": [{"id": "A", "customer_label": "Stage A", "scope": "V1", "milestone_label": "A works"},
                       {"id": "B", "customer_label": "Stage B", "scope": "V1"},
                       {"id": "X", "customer_label": "Later stage", "scope": "LATER"}],
            "criteria": list(items)}
    base.update(top)
    return base


def state_of(registry, cid, **kwargs):
    item = next(c for c in registry["criteria"] if c["id"] == cid)
    return effective_state(item, registry, kwargs.pop("today", TODAY), kwargs.pop("current_version", "v1"), **kwargs)


# ---- the shipped registry ------------------------------------------------------------
def test_shipped_registry_reproduces_the_frozen_baseline():
    result = compute(load_registry(), today=TODAY)
    overall = result["overall"]
    assert (overall["total"], overall["verified"], overall["in_progress"], overall["blocked"],
            overall["unknown_remaining"]) == (50, 20, 7, 10, 13)
    assert (overall["verified_percent"], overall["in_progress_percent"], overall["blocked_percent"],
            overall["unknown_remaining_percent"]) == (40.0, 14.0, 20.0, 26.0)
    assert result["criteria_total"] == 58
    assert (result["first_real_use"]["verified"], result["first_real_use"]["total"]) == (20, 58)
    milestone = result["next_milestone"]
    assert milestone["stage"] == "WINDOWS_EXE" and milestone["customer_label"] == "Windows app starts cleanly"
    assert (milestone["verified"], milestone["total"], milestone["in_progress"], milestone["blocked"]) == (0, 10, 3, 6)
    per_stage = {s["stage"]["id"]: (s["summary"]["verified"], s["summary"]["total"]) for s in result["stages"]}
    assert per_stage["LEDGER"] == (8, 10) and per_stage["RELIABLE_AUTOMATION"] == (4, 10)
    assert per_stage["GOLDEN"] == (2, 4) and per_stage["HUB"] == (6, 8)
    assert per_stage["WINDOWS_EXE"] == (0, 10) and per_stage["CLEAN_MACHINE"] == (0, 8)
    assert result["evaluated"] and not any(row["regress_reasons"] for row in result["evaluated"])


def test_shipped_registry_has_every_field_stage_and_extension_point():
    registry = load_registry()
    for item in registry["criteria"]:
        assert all(field in item for field in REQUIRED_FIELDS), item["id"]
    ids = [stage["id"] for stage in registry["stages"]]
    assert ids[:6] == ["LEDGER", "RELIABLE_AUTOMATION", "GOLDEN", "HUB", "WINDOWS_EXE", "CLEAN_MACHINE"]
    for extension in ("REAL_ADAPTERS", "SPIDER", "INTERFACE", "SETUP", "COMMUNICATION", "PROVIDER_ACCOUNTS",
                      "SAFETY_GATES"):
        assert extension in ids
    assert "percent" not in readiness.DEFAULT_REGISTRY.read_text(encoding="utf-8").replace("percentage is stored", "")


def test_shipped_registry_parses_identically_as_yaml():
    yaml = pytest.importorskip("yaml")
    text = readiness.DEFAULT_REGISTRY.read_text(encoding="utf-8")
    assert yaml.safe_load(text) == json.loads(text)


# ---- percentages derive only from the registry ---------------------------------------
def test_percentages_follow_the_registry_and_nothing_else():
    registry = reg(crit("a1", state="VERIFIED"), crit("a2"), crit("b1", "B"), crit("b2", "B"))
    assert compute(registry, today=TODAY)["overall"]["verified_percent"] == 25.0
    registry["criteria"][1] = crit("a2", state="VERIFIED")
    assert compute(registry, today=TODAY)["overall"]["verified_percent"] == 50.0


@pytest.mark.parametrize("where", ["registry", "stage", "criterion"])
def test_hand_typed_numbers_are_refused(where):
    registry = reg(crit("a1"))
    target = {"registry": registry, "stage": registry["stages"][0], "criterion": registry["criteria"][0]}[where]
    target["verified_percent"] = 99
    with pytest.raises(ValueError):
        compute(registry, today=TODAY)


@pytest.mark.parametrize("count", [1, 3, 7, 13, 58])
def test_segments_always_sum_to_the_whole(count):
    states = [readiness.STATES[i % len(readiness.STATES)] for i in range(count)]
    s = summarize(states)
    assert s["verified"] + s["in_progress"] + s["blocked"] + s["unknown_remaining"] == s["total"] == count
    total = s["verified_percent"] + s["in_progress_percent"] + s["blocked_percent"] + s["unknown_remaining_percent"]
    assert round(total, 1) == 100.0


# ---- green means accepted evidence; it can be lost ------------------------------------
def test_code_present_never_counts_as_verified():
    registry = reg(crit("a1", state="VERIFIED", evidence_level="E2"))
    state, reasons = state_of(registry, "a1")
    assert state == "IN_PROGRESS" and "below the required" in reasons[0]


@pytest.mark.parametrize("change, expected", [
    ({"evidence_sha": None}, "UNKNOWN"),
    ({"evidence_ref": ""}, "UNKNOWN"),
    ({"invalidated": True}, "UNKNOWN"),
    ({"contradicted_by": "run 77"}, "UNKNOWN"),
    ({"blocker": "launcher changed"}, "BLOCKED"),
    ({"definition_rev": 2}, "UNKNOWN"),
])
def test_verified_regresses_when_the_proof_goes_away(change, expected):
    registry = reg(crit("a1", state="VERIFIED", **change))
    state, reasons = state_of(registry, "a1")
    assert state == expected and reasons
    assert compute(registry, today=TODAY)["overall"]["verified"] == 0


def test_stale_evidence_regresses_and_fresh_evidence_does_not():
    registry = reg(crit("a1", state="VERIFIED"))
    assert state_of(registry, "a1", today=datetime.date(2026, 10, 31))[0] == "VERIFIED"
    state, reasons = state_of(registry, "a1", today=datetime.date(2026, 11, 1))
    assert state == "UNKNOWN" and "days old" in reasons[0]


def test_version_change_regresses_only_when_relevant_files_changed():
    registry = reg(crit("a1", state="VERIFIED"))
    assert state_of(registry, "a1", current_version="v2", changed_paths=["docs/readme.md"])[0] == "VERIFIED"
    state, reasons = state_of(registry, "a1", current_version="v2", changed_paths=["src/core/x.py"])
    assert state == "UNKNOWN" and "src/core/x.py changed since v1" in reasons[0]
    # Unknown relevance is never assumed to be fine.
    assert state_of(registry, "a1", current_version="v2")[0] == "UNKNOWN"
    registry["criteria"][0]["freshness"]["watch_paths"] = []
    assert state_of(registry, "a1", current_version="v2", changed_paths=[])[0] == "UNKNOWN"


def test_progress_number_goes_down_and_says_why():
    registry = reg(crit("a1", state="VERIFIED"), crit("a2", state="VERIFIED"))
    before = compute(registry, today=TODAY)["overall"]["verified_percent"]
    registry["criteria"][0]["invalidated"] = True
    result = compute(registry, today=TODAY)
    assert before == 100.0 and result["overall"]["verified_percent"] == 50.0
    view = customer_view(result)
    assert view["reconfirmation_note"] == "1 check needs re-confirming after a change"
    assert dev_view(result, registry)["regression_log"] == ["a1: evidence invalidated"]


def test_blocked_does_not_count_as_verified():
    registry = reg(crit("a1", state="BLOCKED"), crit("a2", state="VERIFIED"))
    overall = compute(registry, today=TODAY)["overall"]
    assert (overall["verified"], overall["blocked"], overall["verified_percent"], overall["blocked_percent"]) == (1, 1, 50.0, 50.0)


def test_unknown_and_not_started_stay_visible():
    registry = reg(crit("a1", state="UNKNOWN"), crit("a2"), crit("a3", state="VERIFIED"))
    result = compute(registry, today=TODAY)
    assert result["overall"]["unknown_remaining"] == 2
    view = customer_view(result)
    statuses = [item["status"] for stage in view["stages"] for sub in stage["substages"] for item in sub["items"]]
    assert statuses.count("unknown") == 2 and view["not_started_or_unknown_percent"] > 0
    tree = customer_tree(view)
    assert "? label a1" in tree and "? label a2" in tree and "✓ label a3" in tree


# ---- parent derives from children; milestones --------------------------------------
def test_stage_state_derives_from_its_criteria():
    registry = reg(crit("a1", state="VERIFIED"), crit("a2", state="VERIFIED"),
                   crit("b1", "B", state="VERIFIED"), crit("b2", "B", state="BLOCKED"))
    stages = {s["stage"]["id"]: s["state"] for s in compute(registry, today=TODAY)["stages"]}
    assert stages == {"A": "VERIFIED", "B": "BLOCKED", "X": "NOT_STARTED"}
    registry["criteria"][3] = crit("b2", "B", state="IN_PROGRESS")
    assert {s["stage"]["id"]: s["state"] for s in compute(registry, today=TODAY)["stages"]}["B"] == "IN_PROGRESS"


def test_next_milestone_is_the_declared_gate_until_it_is_proven():
    registry = reg(crit("a1"), crit("b1", "B"), next_gate="B")
    assert compute(registry, today=TODAY)["next_milestone"]["stage"] == "B"
    registry["criteria"][1] = crit("b1", "B", state="VERIFIED")
    milestone = compute(registry, today=TODAY)["next_milestone"]
    assert milestone["stage"] == "A" and milestone["customer_label"] == "A works"
    registry["criteria"][0] = crit("a1", state="VERIFIED")
    assert compute(registry, today=TODAY)["next_milestone"] is None


def test_empty_extension_stage_is_neither_counted_nor_shown_to_customers():
    registry = reg(crit("a1", state="VERIFIED"))
    result = compute(registry, today=TODAY)
    assert result["overall"]["total"] == 1
    assert [stage["label"] for stage in customer_view(result)["stages"]] == ["Stage A"]


def test_later_scope_is_listed_apart_from_the_headline_number():
    registry = reg(crit("a1", state="VERIFIED"), crit("x1", "X"))
    result = compute(registry, today=TODAY)
    view = customer_view(result)
    assert result["overall"]["total"] == 1 and view["verified_percent"] == 100.0
    assert view["after_this"] == [{"label": "Later stage", "checks_verified": 0, "checks_total": 1}]


# ---- two audiences, one truth ----------------------------------------------------------
def test_customer_view_carries_no_engineering_jargon():
    registry = load_registry()
    text = json.dumps(customer_view(compute(registry, today=TODAY)), ensure_ascii=False)
    for item in registry["criteria"]:
        assert item["id"] not in text
        for field in ("evidence_ref", "evidence_sha", "title"):
            assert not item.get(field) or item[field] not in text
    for word in ("evidence", "sha", "owner", "PR #", "E3", "E4", "CI", "integration/v1", "pid"):
        assert word not in text
    # The status word is "verified", never "done" or "complete".
    view = customer_view(compute(registry, today=TODAY))
    statuses = {stage["status"] for stage in view["stages"]}
    statuses |= {item["status"] for stage in view["stages"] for sub in stage["substages"] for item in sub["items"]}
    assert statuses <= {"verified", "working", "blocked", "unknown"}
    for line in (view["headline"], view["segments"]):
        assert "done" not in line.lower() and "complete" not in line.lower()


def test_customer_tree_uses_the_frozen_wording():
    tree = customer_tree(customer_view(compute(load_registry(), today=TODAY)))
    assert tree.splitlines()[0] == "Project readiness: 40% verified"
    assert "Verified 40 · Working on 14 · Blocked 20 · Not started 26" in tree
    assert 'Next milestone: "Windows app starts cleanly", 0 of 10 checks verified · 3 being worked on · 6 waiting on fixes' in tree
    assert "Needs you: none" in tree


def test_needs_you_appears_only_for_open_human_owned_checks():
    registry = reg(crit("a1", owner="founder"), crit("a2", state="VERIFIED", owner="founder"), crit("a3"))
    view = customer_view(compute(registry, today=TODAY))
    assert view["needs_you"] == ["label a1"]
    assert "label a1  [Needs You]" in customer_tree(view)


def test_dev_view_shows_what_engineers_need():
    registry = load_registry()
    view = dev_view(compute(registry, today=TODAY), registry)
    item = view["stages"][0]["substages"][0]["items"][0]
    for field in ("id", "required_evidence_level", "evidence_level", "evidence_ref", "evidence_sha", "owner",
                  "freshness", "blocker", "next_action", "effective_state", "declared_state"):
        assert field in item
    assert item["freshness"]["age_days"] == 0 and item["freshness"]["expires_in_days"] == 30
    tree = dev_tree(view)
    assert "verified 20/50 = 40.0%" in tree and "Next gate WINDOWS_EXE: 0/10 verified" in tree


def test_evidence_about_to_go_stale_is_flagged_for_engineers():
    registry = reg(crit("a1", state="VERIFIED"))
    view = dev_view(compute(registry, today=datetime.date(2026, 10, 30)), registry)
    assert view["evidence_stale_within_a_day"] == ["a1"]


# ---- determinism and input hygiene ---------------------------------------------------
def test_same_inputs_give_identical_output(capsys):
    registry = load_registry()
    first = json.dumps(dev_view(compute(copy.deepcopy(registry), today=TODAY), registry), sort_keys=True)
    second = json.dumps(dev_view(compute(copy.deepcopy(registry), today=TODAY), registry), sort_keys=True)
    assert first == second
    assert readiness.main(["--view", "customer", "--format", "json", "--today", "2026-10-02"]) == 0
    assert json.loads(capsys.readouterr().out)["headline"] == "40% verified"


def test_in_flight_is_accepted_as_in_progress():
    registry = reg(crit("a1", state="IN_FLIGHT"))
    assert compute(registry, today=TODAY)["overall"]["in_progress"] == 1


@pytest.mark.parametrize("breakage", ["duplicate", "unknown_stage", "unknown_state", "blocked_without_blocker",
                                      "unknown_gate", "unknown_level"])
def test_broken_registries_are_refused(breakage):
    registry = reg(crit("a1"), crit("a2"))
    if breakage == "duplicate":
        registry["criteria"][1]["id"] = "a1"
    elif breakage == "unknown_stage":
        registry["criteria"][0]["stage"] = "NOPE"
    elif breakage == "unknown_state":
        registry["criteria"][0]["state"] = "DONE"
    elif breakage == "blocked_without_blocker":
        registry["criteria"][0]["state"] = "BLOCKED"
    elif breakage == "unknown_gate":
        registry["next_gate"] = "NOPE"
    else:
        registry["criteria"][0]["required_evidence_level"] = "E9"
    with pytest.raises(ValueError):
        validate(registry)
