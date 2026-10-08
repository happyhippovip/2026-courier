"""Short-video mission template validator (fail closed).

Validates ``missions/templates/short_video.json`` and enforces the ordered
9-step pipeline:

    idea -> script -> scene_bind -> render -> mux_audio -> verify
        -> publish_gate -> publish -> receipt

Rules (fail closed, no default PASS):
- the template must list exactly these steps in exactly this order;
- ``publish_gate`` must require explicit human approval;
- ``publish`` is reachable only with recorded human approval of the gate;
- steps cannot be skipped, reordered, or repeated; unknown steps rejected.

Pure functions only: no I/O except load_template, no network, no side effects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

CANONICAL_STEPS: tuple[str, ...] = (
    "idea",
    "script",
    "scene_bind",
    "render",
    "mux_audio",
    "verify",
    "publish_gate",
    "publish",
    "receipt",
)

PUBLISH_GATE_STEP = "publish_gate"
PUBLISH_STEP = "publish"
HUMAN_APPROVAL = "explicit_human_approval"


class ShortVideoError(ValueError):
    """Raised when a template cannot even be loaded (missing/unparseable)."""


def template_path() -> Path:
    """Filesystem path of the canonical template next to this module."""
    return Path(__file__).resolve().parent.parent / "missions" / "templates" / "short_video.json"


def load_template(path: str | Path) -> dict:
    """Load and parse a template file; fail closed on any load problem."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ShortVideoError(f"template not readable: {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ShortVideoError(f"template not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ShortVideoError(f"template must be a JSON object: {path}")
    return data


def validate_template(data: Mapping) -> list[str]:
    """Return a list of violations; empty means the template is valid."""
    errors: list[str] = []
    if not isinstance(data, Mapping):
        return ["template must be a mapping"]
    steps = data.get("production_steps")
    if steps != list(CANONICAL_STEPS):
        errors.append(
            "production_steps must be exactly "
            f"{list(CANONICAL_STEPS)} in order, got {steps!r}"
        )
    gate = data.get("publish_gate")
    if not isinstance(gate, Mapping):
        errors.append("publish_gate must be a mapping")
    else:
        if gate.get("step") != PUBLISH_GATE_STEP:
            errors.append(f"publish_gate.step must be {PUBLISH_GATE_STEP!r}")
        if gate.get("requires") != HUMAN_APPROVAL:
            errors.append(f"publish_gate.requires must be {HUMAN_APPROVAL!r}")
        if gate.get("guards_step") != PUBLISH_STEP:
            errors.append(f"publish_gate.guards_step must be {PUBLISH_STEP!r}")
    policy = data.get("zero_cost_policy")
    if policy != "ZERO_COST_ONLY":
        errors.append(f"zero_cost_policy must be 'ZERO_COST_ONLY', got {policy!r}")
    return errors


def is_valid(data: Mapping) -> bool:
    """True only when validate_template reports no violations."""
    return validate_template(data) == []


def requires_human_approval(data: Mapping) -> bool:
    """True unless the template explicitly documents otherwise; fail closed."""
    gate = data.get("publish_gate") if isinstance(data, Mapping) else None
    if not isinstance(gate, Mapping):
        return True
    return gate.get("requires", HUMAN_APPROVAL) != "none"


def can_advance(
    data: Mapping,
    completed: list[str],
    step: str,
    approvals: Mapping | None = None,
) -> tuple[bool, str]:
    """Check whether ``step`` may run next after ``completed`` steps.

    Returns (allowed, reason). ``approvals`` maps gate names to recorded
    human-approval evidence, e.g. {"publish_gate": "human:2026-10-08/..."}.
    """
    if validate_template(data):
        return False, "template invalid"
    if step not in CANONICAL_STEPS:
        return False, f"unknown step {step!r}"
    expected = CANONICAL_STEPS[len(completed)] if len(completed) < len(CANONICAL_STEPS) else None
    if expected is None:
        return False, "pipeline already complete"
    if step != expected:
        return False, f"expected next step {expected!r}, got {step!r}"
    if len(set(completed)) != len(completed):
        return False, "completed steps contain a duplicate"
    if step == PUBLISH_STEP:
        gate_approval = (approvals or {}).get(PUBLISH_GATE_STEP)
        if not gate_approval:
            return False, "publish requires recorded human approval at publish_gate"
    return True, "ok"
