"""Direct Controller.create_task versus the shared handoff decision.

``create_task`` is L2. PR #826 edits ``courier_core/controller.py`` for boot and
the verifier, not for cost. PR #830 pins the same hole as F-C1 and names L2.
There is no writer lease on this file, so this lane does not patch it.

The strict xfail is the handoff. It becomes a failure when ``create_task``
starts refusing the same bodies ``handoff_spend_block`` already refuses. L2
removes the marker in the same change. The call, after params is known to be
a dict and before ``Event(...)``, is::

    reason = handoff_spend_block(body)
    if reason:
        raise ApiError(400, reason, "cost gate refused this task")

Import ``handoff_spend_block`` inside the method so courier_core does not grow
a module-level dependency. Do not default ``local_shell`` to 0. A missing
estimate stays missing. The number the gate reads is ``params.estimated_cost_eur``
because ``_only_fields`` rejects any other cost field. Explicit finite 0 on the
active tier stays allowed. Duplicate replay of an already admitted body stays 200.
"""

import pytest

from courier_core.controller import ApiError, Controller
from scripts.handoff_spend import handoff_spend_block

_L2 = pytest.mark.xfail(
    strict=True,
    reason="L2 owns create_task. F-C1 on PR #830. Call handoff_spend_block before the journal append.",
)


def _body(params=None):
    return {
        "adapter": "synthetic",
        "params": {"unit": "a"} if params is None else params,
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
    }


def _boot(tmp_path):
    return Controller(tmp_path / "home").boot()


def test_shared_decision_blocks_the_bodies_the_controller_still_accepts():
    missing = _body()
    marked = _body({"unit": "a", "estimated_cost_eur": 0.0, "unknown_cost": True})
    unknown_class = _body({"unit": "a", "estimated_cost_eur": 0.0, "cost_class": "unknown"})
    negative = _body({"estimated_cost_eur": -1.0})
    positive = _body({"estimated_cost_eur": 1.0})
    local_shell = {
        "adapter": "local_shell",
        "params": {"command": ["agy", "--print"], "write": "out.txt"},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
    }
    assert handoff_spend_block(missing) == "UNKNOWN_COST"
    assert handoff_spend_block(marked) == "UNKNOWN_COST"
    assert handoff_spend_block(unknown_class) == "UNKNOWN_COST"
    assert handoff_spend_block(negative) == "UNKNOWN_COST"
    assert handoff_spend_block(positive) == "SPEND_NOT_ALLOWED_BY_POLICY"
    assert handoff_spend_block(local_shell) == "UNKNOWN_COST"
    assert handoff_spend_block(_body({"estimated_cost_eur": 0.0})) is None


@_L2
def test_create_task_rejects_a_missing_estimate(tmp_path):
    ctrl = _boot(tmp_path)
    try:
        with pytest.raises(ApiError) as caught:
            ctrl.create_task(_body())
        assert caught.value.status == 400
        assert caught.value.code == "UNKNOWN_COST"
        assert list(ctrl.journal.events()) == []
    finally:
        ctrl.stop()


@_L2
def test_create_task_rejects_an_unknown_mark_beside_zero(tmp_path):
    ctrl = _boot(tmp_path)
    try:
        with pytest.raises(ApiError) as caught:
            ctrl.create_task(_body({"unit": "a", "estimated_cost_eur": 0.0, "unknown_cost": True}))
        assert caught.value.code == "UNKNOWN_COST"
    finally:
        ctrl.stop()


@_L2
def test_create_task_rejects_a_positive_estimate(tmp_path):
    ctrl = _boot(tmp_path)
    try:
        with pytest.raises(ApiError) as caught:
            ctrl.create_task(_body({"estimated_cost_eur": 1.0}))
        assert caught.value.code == "SPEND_NOT_ALLOWED_BY_POLICY"
    finally:
        ctrl.stop()


@_L2
def test_create_task_does_not_treat_local_shell_as_free(tmp_path):
    ctrl = _boot(tmp_path)
    try:
        body = {
            "adapter": "local_shell",
            "params": {"command": ["agy", "--print"], "write": "out.txt"},
            "effect_class": "idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 30,
        }
        with pytest.raises(ApiError) as caught:
            ctrl.create_task(body)
        assert caught.value.code == "UNKNOWN_COST"
        assert list(ctrl.journal.events()) == []
    finally:
        ctrl.stop()


def test_create_task_accepts_an_explicit_zero_in_params(tmp_path):
    ctrl = _boot(tmp_path)
    try:
        status, payload = ctrl.create_task(_body({"estimated_cost_eur": 0.0}))
        assert status == 201
        assert payload["duplicate"] is False
        again, replay = ctrl.create_task({
            **_body({"estimated_cost_eur": 0.0}),
            "idempotency_key": "same-body",
        })
        assert again == 201
        status2, replay2 = ctrl.create_task({
            **_body({"estimated_cost_eur": 0.0}),
            "idempotency_key": "same-body",
        })
        assert status2 == 200
        assert replay2["duplicate"] is True
        assert replay["task_id"] == replay2["task_id"]
    finally:
        ctrl.stop()
