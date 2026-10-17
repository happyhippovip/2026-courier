"""Focused tests for the short-video mission template + validator (P2)."""

import copy

import pytest

from courier_core.short_video import (
    CANONICAL_STEPS,
    PUBLISH_GATE_STEP,
    PUBLISH_STEP,
    ShortVideoError,
    can_advance,
    is_valid,
    load_template,
    requires_human_approval,
    template_path,
    validate_template,
)

EXPECTED_STEPS = [
    "idea",
    "script",
    "scene_bind",
    "render",
    "mux_audio",
    "verify",
    "publish_gate",
    "publish",
    "receipt",
]


def _repo_template():
    return load_template(template_path())


def test_canonical_step_order():
    assert list(CANONICAL_STEPS) == EXPECTED_STEPS


def test_repo_template_valid():
    data = _repo_template()
    assert validate_template(data) == []
    assert is_valid(data) is True


def test_repo_template_publish_gate_requires_human():
    data = _repo_template()
    assert data["publish_gate"]["requires"] == "explicit_human_approval"
    assert requires_human_approval(data) is True


def test_reordered_steps_rejected():
    data = _repo_template()
    steps = list(data["production_steps"])
    steps[3], steps[4] = steps[4], steps[3]  # swap render/mux_audio
    data["production_steps"] = steps
    assert validate_template(data) != []
    assert is_valid(data) is False


def test_missing_publish_gate_rejected_and_fail_closed():
    data = _repo_template()
    del data["publish_gate"]
    assert validate_template(data) != []
    assert requires_human_approval(data) is True


def test_unknown_step_rejected():
    data = _repo_template()
    data["production_steps"] = list(data["production_steps"]) + ["broadcast"]
    assert validate_template(data) != []


def test_full_walk_with_approval():
    data = _repo_template()
    completed: list[str] = []
    approvals = {PUBLISH_GATE_STEP: "human:2026-10-08/ok"}
    for step in EXPECTED_STEPS:
        allowed, reason = can_advance(data, completed, step, approvals)
        assert allowed, f"{step}: {reason}"
        completed.append(step)
    allowed, _ = can_advance(data, completed, "receipt", approvals)
    assert allowed is False


def test_publish_without_approval_refused():
    data = _repo_template()
    completed = EXPECTED_STEPS[: EXPECTED_STEPS.index(PUBLISH_STEP)]
    allowed, reason = can_advance(data, completed, PUBLISH_STEP, {})
    assert allowed is False
    assert "approval" in reason


def test_skipped_step_refused():
    data = _repo_template()
    allowed, _ = can_advance(data, ["idea"], "scene_bind", {})
    assert allowed is False


def test_unknown_step_advance_refused():
    data = _repo_template()
    allowed, _ = can_advance(data, [], "broadcast", {})
    assert allowed is False


def test_invalid_template_blocks_all_advance():
    data = _repo_template()
    data["production_steps"] = ["idea"]
    allowed, reason = can_advance(data, [], "idea", {})
    assert allowed is False
    assert reason == "template invalid"


def test_load_missing_file_raises():
    with pytest.raises(ShortVideoError):
        load_template(template_path().parent / "does_not_exist.json")


def test_load_malformed_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ShortVideoError):
        load_template(bad)


def test_template_mutation_does_not_leak_between_tests():
    first = _repo_template()
    first["production_steps"].append("x")
    assert _repo_template()["production_steps"] == EXPECTED_STEPS
    assert copy.deepcopy(first) != _repo_template()
