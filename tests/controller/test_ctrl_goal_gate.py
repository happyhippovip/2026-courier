"""create_task and claim dispatch only a task a confirmed contract accepts."""

import pytest

from ctrl_helpers import LiveService, make_controller, task_body
from courier_core.controller import ApiError
from courier_core.goal_contract import GOAL_CONTRACTS_FILE, draft_goal_contract
from tests.dispatch_contract import FIXTURE_HUMAN_TOKEN, task_view


def _legacy(**overrides):
    body = {"adapter": "probe", "params": {"x": 1}, "effect_class": "idempotent",
            "max_attempts": 3, "lease_ttl_s": 6}
    body.update(overrides)
    return body


@pytest.fixture
def ctl(tmp_path):
    controller = make_controller(tmp_path / "home")
    yield controller
    controller.stop()


def api_error(fn, *args, **kwargs):
    with pytest.raises(ApiError) as info:
        fn(*args, **kwargs)
    return info.value


def _created(ctl):
    return [event for event in ctl.journal.events() if event.type.value == "TASK_CREATED"]


def test_missing_or_contradictory_goal_is_not_dispatched(ctl):
    for goal in (None, {}, "", {"goal_id": "goal-dispatch"},
                 "fix the bug or maybe rewrite the module"):
        err = api_error(ctl.create_task, _legacy(goal=goal))
        assert err.status == 409 and err.code == "needs_clarification"
        assert err.extra["outcome"] == "NEEDS_CLARIFICATION"
    assert _created(ctl) == []
    assert ctl.claim({"worker_id": "w1"}) is None


def test_free_text_with_or_or_either_is_a_draft_awaiting_confirmation(ctl):
    for goal in ("ship the report or the summary", "deliver either artifact"):
        status, body = ctl.create_task(_legacy(goal=goal))
        assert status == 200
        assert body["outcome"] == "DRAFTED"
        assert body["confirmed"] is False
        assert body["dispatched"] is False
        assert "task_id" not in body
    assert _created(ctl) == []
    assert ctl.claim({"worker_id": "w1"}) is None
    assert not (ctl.home / GOAL_CONTRACTS_FILE).read_text(encoding="utf-8").count("ship the report")


def test_unconfirmed_contract_is_not_dispatched(ctl):
    draft = draft_goal_contract("ship the report or the summary")
    contract = draft.contract
    body = _legacy(**{
        "goal_id": contract.goal_id,
        "goal_fingerprint": contract.fingerprint(),
        "scope": ["stated-result"],
        "acceptance_ids": ["stated-result"],
        "evidence_class": "deterministic",
    })
    err = api_error(ctl.create_task, body)
    assert err.status == 409 and err.code == "goal_contract_rejected"
    assert err.extra["outcome"] == "NOT_VERIFIABLE"
    assert "missing_contract" in err.extra["reasons"]
    assert _created(ctl) == []
    assert ctl.claim({"worker_id": "w1"}) is None


def test_anonymous_and_agent_confirmation_is_refused_and_not_stored(ctl, monkeypatch):
    monkeypatch.setenv("COURIER_HUMAN_CONFIRM_TOKEN", FIXTURE_HUMAN_TOKEN)
    goal = "ship the report or the summary"
    before = (ctl.home / GOAL_CONTRACTS_FILE).read_bytes()
    err = api_error(ctl.confirm_goal, {
        "goal": goal, "actor_ref": "person:ada", "at": "2026-10-15T12:00:00Z", "authenticated": True,
    })
    assert err.status == 403
    for actor in ("anonymous", "agent:bot"):
        err = api_error(
            ctl.confirm_goal,
            {"goal": goal, "actor_ref": actor, "at": "2026-10-15T12:00:00Z", "authenticated": True},
            human_token=FIXTURE_HUMAN_TOKEN,
        )
        assert err.status == 403
    monkeypatch.setenv("COURIER_HUMAN_CONFIRM_TOKEN", "worker-token")
    err = api_error(
        ctl.confirm_goal,
        {"goal": goal, "actor_ref": "person:ada", "at": "2026-10-15T12:00:00Z", "authenticated": True},
        human_token="worker-token",
        service_token="worker-token",
    )
    assert err.status == 403
    assert (ctl.home / GOAL_CONTRACTS_FILE).read_bytes() == before
    assert _created(ctl) == []


def test_human_confirmation_then_validate_task_dispatches(ctl, monkeypatch):
    monkeypatch.setenv("COURIER_HUMAN_CONFIRM_TOKEN", FIXTURE_HUMAN_TOKEN)
    goal = "ship the report or the summary"
    confirmed = ctl.confirm_goal({
        "goal": goal, "actor_ref": "person:ada", "at": "2026-10-15T12:00:00Z", "authenticated": False,
    }, human_token=FIXTURE_HUMAN_TOKEN)
    assert confirmed["confirmed"] is True
    draft = draft_goal_contract(goal)
    assert confirmed["goal_fingerprint"] == draft.contract.fingerprint()
    status, body = ctl.create_task(_legacy(
        goal_id=confirmed["goal_id"],
        goal_fingerprint=confirmed["goal_fingerprint"],
        scope=["stated-result"],
        acceptance_ids=["stated-result"],
        evidence_class="deterministic",
    ))
    assert status == 201
    lease = ctl.claim({"worker_id": "w1"})
    assert lease is not None and lease["task_id"] == body["task_id"]


def test_scope_widened_is_not_dispatched(ctl):
    err = api_error(ctl.create_task, task_body(scope=["production"]))
    assert err.status == 409 and err.code == "goal_contract_rejected"
    assert err.extra["outcome"] == "HUMAN_CONFIRMATION_REQUIRED"
    assert "scope_widened" in err.extra["reasons"]
    assert _created(ctl) == []
    assert ctl.claim({"worker_id": "w1"}) is None


def test_stale_fingerprint_is_not_dispatched(ctl):
    err = api_error(ctl.create_task, task_body(goal_fingerprint="ab" * 32))
    assert err.status == 409 and err.code == "goal_contract_rejected"
    assert err.extra["outcome"] == "REVALIDATION_REQUIRED"
    assert "stale_fingerprint" in err.extra["reasons"]
    assert _created(ctl) == []
    assert ctl.claim({"worker_id": "w1"}) is None


def test_claim_does_not_dispatch_a_journaled_legacy_task(ctl):
    from courier_core.events import Event, EventType
    ctl.journal.append(Event(type=EventType.TASK_CREATED, task_id="legacy-1", payload={
        "adapter": "probe", "params": {"x": 1}, "effect_class": "idempotent",
        "max_attempts": 1, "lease_ttl_s": 6,
    }))
    assert ctl.claim({"worker_id": "w1"}) is None


def test_legacy_task_without_a_contract_is_not_dispatched(ctl):
    for body in (
        _legacy(),
        _legacy(params={"goal_id": "goal-dispatch", "goal_fingerprint": "ab" * 32, "unit": "a"}),
    ):
        err = api_error(ctl.create_task, body)
        assert err.status == 409 and err.code == "goal_contract_rejected"
        assert err.extra["outcome"] == "NOT_VERIFIABLE"
        assert "missing_contract" in err.extra["reasons"]
    assert _created(ctl) == []
    assert ctl.claim({"worker_id": "w1"}) is None


def test_agent_service_token_cannot_confirm_as_person(tmp_path, monkeypatch):
    """An agent that holds the worker token and names person:x stores nothing."""
    monkeypatch.setenv("COURIER_HUMAN_CONFIRM_TOKEN", FIXTURE_HUMAN_TOKEN)
    live = LiveService(tmp_path / "home")
    try:
        path = live.controller.home / GOAL_CONTRACTS_FILE
        before = path.read_bytes()
        body = {
            "goal": "ship the report or the summary",
            "actor_ref": "person:x",
            "at": "2026-10-15T12:00:00Z",
            "authenticated": True,
        }
        refused = live.post("/v1/goals/confirm", body)
        assert refused.status_code == 403
        presented = live.post(
            "/v1/goals/confirm", body,
            headers={"X-Courier-Human-Token": live.service.token},
        )
        assert presented.status_code == 403
        assert path.read_bytes() == before
        accepted = live.post(
            "/v1/goals/confirm",
            {**body, "actor_ref": "person:ada", "authenticated": False},
            headers={"X-Courier-Human-Token": FIXTURE_HUMAN_TOKEN},
        )
        assert accepted.status_code == 200
        assert accepted.json()["confirmed"] is True
        assert path.read_bytes() != before
    finally:
        live.stop()


def test_confirmed_task_view_is_dispatched(ctl):
    status, body = ctl.create_task(task_body())
    assert status == 201
    lease = ctl.claim({"worker_id": "w1"})
    assert lease is not None and lease["task_id"] == body["task_id"]
    assert task_view()["goal_id"] == "goal-dispatch"
