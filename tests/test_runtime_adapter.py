import pytest
from dataclasses import replace

from courier_runtime.adapter import (AdapterSpec, CampaignGrant, CampaignPlan, call, check_launch, promote)
from courier_runtime.grants import Broker, Request


# -- adapter core ------------------------------------------------------------------------

class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


def req(rid, cap="calendar.read", effect="idempotent", res=("cal:work",)):
    return Request(rid, "p1", cap, frozenset(res), "cloud-1", "acct-1", "personal", "read", effect)


@pytest.fixture
def broker():
    b = Broker(Clock())
    b.authorize(req("r0"))
    b.grant(req("r0"), "g1", expires_at=None)
    return b


SPEC = AdapterSpec("calendar", "1", {"calendar.read": "idempotent", "calendar.invite": "non_idempotent"})


def test_adapter_call_within_grant_produces_attributed_evidence(broker):
    r = call(SPEC, broker, req("r1"), lambda q: (True, {"events": 3}, None))
    assert r.status == "DONE" and r.evidence["grant_id"] == "g1" and r.evidence["adapter"] == "calendar@1"


def test_undeclared_capability_and_effect_mismatch_are_refused(broker):
    assert call(SPEC, broker, req("r1", cap="mail.send"), lambda q: (True, {}, None)).status == "REFUSED"
    assert call(SPEC, broker, req("r1", effect="non_idempotent"), lambda q: (True, {}, None)).status == "REFUSED"


def test_adapter_cannot_widen_its_grant(broker):
    executed = []
    r = call(SPEC, broker, req("r2", res=("cal:work", "cal:private")), lambda q: executed.append(q) or (True, {}, None))
    assert r.status == "NEEDS_USER" and executed == []


@pytest.mark.parametrize("failure, status, retry", [
    ("transient", "FAILED", True), ("denied", "FAILED", False),
    ("auth_expired", "NEEDS_USER", False), ("uncertain_effect", "NEEDS_USER", False), ("weird", "NEEDS_USER", False),
])
def test_failure_classes_and_retry_eligibility(broker, failure, status, retry):
    r = call(SPEC, broker, req("r3"), lambda q: (False, {}, failure))
    assert (r.status, r.retry_eligible) == (status, retry)


# -- promote / launch campaign -----------------------------------------------------------

GRANT = CampaignGrant("cg1", "acct-1", "search", "c-hash", "a-hash", frozenset({"DE", "AT"}), 20.0, 300.0,
                      0.0, 30 * 86400.0, frozenset({"create", "pause"}))
PLAN = CampaignPlan("acct-1", "search", "c-hash", "a-hash", frozenset({"DE"}), 10.0, 200.0, 0.0, 20 * 86400.0)


def test_promote_is_preview_only():
    assert promote(PLAN)["effect"] is None


def test_launch_inside_grant_is_allowed_and_without_grant_refused():
    assert check_launch(PLAN, GRANT) == []
    assert check_launch(PLAN, None)


@pytest.mark.parametrize("change", [
    dict(daily_budget=25.0), dict(total_budget=301.0), dict(ad_account="acct-2"),
    dict(audience_hash="a-other"), dict(regions=frozenset({"DE", "US"})), dict(creative_hash="c-new"),
    dict(end=31 * 86400.0), dict(channel="social"),
])
def test_any_change_outside_the_grant_is_rejected(change):
    assert check_launch(replace(PLAN, **change), GRANT)


def test_pause_is_allowed_but_resume_is_not_unless_granted():
    assert check_launch(PLAN, GRANT, action="pause") == []
    assert check_launch(PLAN, GRANT, action="resume")
