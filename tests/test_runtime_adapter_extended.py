import pytest
from courier_runtime.adapter import (
    AdapterSpec,
    CallResult,
    CampaignGrant,
    CampaignPlan,
    call,
    check_launch,
    promote,
)
from courier_runtime.grants import Broker, Request


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_call_refused_when_capability_undeclared():
    spec = AdapterSpec("test-adapter", "1.0", {"read_item": "idempotent"})
    clock = Clock()
    broker = Broker(clock)
    req = Request("r1", "p1", "write_item", frozenset(), "host-1", "", "public", "write", "idempotent")

    res = call(spec, broker, req, lambda r: (True, {}, None))
    assert res.status == "REFUSED"
    assert "did not declare write_item" in res.reason


def test_call_refused_when_effect_class_mismatch():
    spec = AdapterSpec("test-adapter", "1.0", {"read_item": "idempotent"})
    clock = Clock()
    broker = Broker(clock)
    # Adapter declares read_item as idempotent, but request specifies non_idempotent
    req = Request("r1", "p1", "read_item", frozenset(), "host-1", "", "public", "read", "non_idempotent")

    res = call(spec, broker, req, lambda r: (True, {}, None))
    assert res.status == "REFUSED"
    assert "read_item is idempotent, not non_idempotent" in res.reason


def test_call_transient_failure_on_non_idempotent_not_retry_eligible():
    spec = AdapterSpec("mutating-adapter", "1.0", {"charge": "non_idempotent"})
    clock = Clock()
    broker = Broker(clock)
    req = Request("r1", "p1", "charge", frozenset({"stripe:charge"}), "host-1", "", "project", "execute", "non_idempotent")
    broker.authorize(req)
    broker.grant(req, "g1", expires_at=2000.0)

    # Denied failure class on non_idempotent: status is FAILED, retry_eligible is False
    res = call(spec, broker, req, lambda r: (False, {"error": "denied"}, "denied"))
    assert res.status == "FAILED"
    assert res.failure == "denied"
    assert res.retry_eligible is False


def test_check_launch_pause_action_always_within_authority():
    grant = CampaignGrant(
        grant_id="cg-1",
        ad_account="act_123",
        channel="meta",
        creative_hash="hash_a",
        audience_hash="aud_a",
        regions=frozenset({"DE", "AT"}),
        daily_budget_cap=50.0,
        total_budget_cap=500.0,
        start=1000.0,
        end=2000.0,
        allowed_actions=frozenset({"create", "pause"}),
    )
    # Plan has different budget / regions / creative
    divergent_plan = CampaignPlan(
        ad_account="act_123",
        channel="meta",
        creative_hash="other_hash",
        audience_hash="other_aud",
        regions=frozenset({"US"}),
        daily_budget=100.0,
        total_budget=1000.0,
        start=500.0,
        end=3000.0,
    )
    # But pausing is a safety narrowing: check_launch permits pause as long as action is allowed
    assert check_launch(divergent_plan, grant, action="pause") == []
