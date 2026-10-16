"""Catalog 2576–2600: blocked explanation, next action, honest continuation.

The hub projection is pure. These cases use recorded events only. A scheduled
retry is not a resumption, and a blocked card must name the action and the
person's decision without the controller's internal reason.
"""

from courier_hub import model

INTERNAL_REASON = (
    "outcome of non_idempotent attempt 2 is unknown (lease lost); needs a human decision"
)
FORBIDDEN = ("attempt", "lease", "BLOCKED", "dispatch", "effect_key", "non_idempotent", "worker")


def _task(**kw):
    base = {
        "task_id": "t-night",
        "status": "QUEUED",
        "adapter": "synthetic",
        "params": {"title": "Overnight file"},
        "effect_class": "idempotent",
        "attempt": 2,
    }
    base.update(kw)
    return base


def _event(kind, **payload):
    return {"type": kind, "ts_utc": "2026-10-13T02:00:00Z", "payload": payload}


def _scheduled_only():
    return [
        _event("TASK_CREATED"),
        _event("TASK_STARTED"),
        _event("LEASE_EXPIRED"),
        _event("TASK_RETRY_SCHEDULED", reason="lease expired"),
    ]


def _customer_text(value, key=None):
    if isinstance(value, dict):
        return " ".join(_customer_text(v, k) for k, v in value.items() if k not in {"blocked_attempt", "id"})
    if isinstance(value, list):
        return " ".join(_customer_text(v, key) for v in value)
    return value if isinstance(value, str) else ""


def test_scheduled_retry_is_not_described_as_resumed():
    task = _task(status="QUEUED")
    events = _scheduled_only()
    first = model.receipt(task, events)
    again = model.receipt(task, list(events))
    assert first == again
    assert first["resumed"] is False
    tried = " ".join(step["what"] for step in first["tried"])
    assert "resumed" not in tried.lower()
    assert "planned another try" in tried.lower()


def test_work_that_starts_again_is_a_resumption():
    events = _scheduled_only() + [_event("TASK_CLAIMED"), _event("TASK_STARTED")]
    receipt = model.receipt(_task(status="RUNNING"), events)
    assert receipt["resumed"] is True
    assert "resumed" not in " ".join(step["what"] for step in receipt["tried"]).lower()


def test_a_question_cancels_the_resumption_claim():
    events = _scheduled_only() + [_event("TASK_BLOCKED", reason=INTERNAL_REASON)]
    receipt = model.receipt(_task(status="BLOCKED", effect_class="non_idempotent"), events)
    assert receipt["resumed"] is False


def test_started_then_blocked_is_not_still_called_resumed():
    events = _scheduled_only() + [
        _event("TASK_STARTED"),
        _event("TASK_BLOCKED", reason=INTERNAL_REASON),
    ]
    receipt = model.receipt(_task(status="BLOCKED", effect_class="non_idempotent"), events)
    assert receipt["resumed"] is False


def test_blocked_card_names_the_action_and_hides_the_internal_reason():
    task = _task(status="BLOCKED", effect_class="non_idempotent", adapter="synthetic")
    events = [_event("TASK_BLOCKED", reason=INTERNAL_REASON)]
    card = model.card(task, events)
    why = card["needs_you"]["why"]
    assert "write the test file" in why
    shown = _customer_text([card, model.receipt(task, events)])
    for word in FORBIDDEN:
        assert word not in shown
    assert INTERNAL_REASON not in shown
    assert model.support(task, events)["events"][0]["type"] == "TASK_BLOCKED"


def test_needs_you_names_the_persons_decision_as_the_next_action():
    task = _task(status="BLOCKED", effect_class="non_idempotent")
    events = [_event("TASK_BLOCKED", reason=INTERNAL_REASON)]
    card = model.card(task, events)
    assert card == model.card(task, list(events))
    next_action = card["needs_you"]["next"]
    assert card["next"] == next_action
    assert "your decision" in next_action
    assert "will not continue" in next_action
    other = model.needs_you_card(_task(status="BLOCKED", adapter="other", effect_class="non_idempotent"), [])
    assert "carry out the action" in other["why"]
    assert other["next"] == next_action


def test_unrecognised_receipt_does_not_call_a_schedule_a_resumption():
    task = {"task_id": "t-odd", "status": "TELEPORTED", "adapter": "synthetic", "params": {}}
    receipt = model.unrecognised_receipt(task, _scheduled_only())
    assert receipt["resumed"] is False


def test_needs_you_renderer_shows_the_next_action():
    import os
    import shutil
    import subprocess

    node = shutil.which("node") or shutil.which("node.cmd") or shutil.which("node.exe")
    if not node:
        pytest.skip("node is not installed")

    script = """
import { renderCard } from './courier_hub/static/hub_core.mjs';
import { readFileSync } from 'node:fs';
const view = JSON.parse(readFileSync('tests/desktop/fixtures/home_view.json', 'utf8'));
const html = renderCard(view.needs_you[0], { now: Date.parse('2026-10-02T08:05:00Z') });
const next = 'The next step is your decision. Courier will not continue this on its own.';
const why = 'Courier lost contact while trying to write the test file';
if (!html.includes(next) || !html.includes(why)) {
  console.error(html);
  process.exit(1);
}
"""
    result = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, check=False, shell=(os.name == "nt"))
    assert result.returncode == 0, result.stdout + result.stderr

