import pytest
from dataclasses import replace

from courier_runtime.adapter import (
    FAILURE_CLASSES,
    AdapterSpec,
    CallResult,
    CampaignGrant,
    CampaignPlan,
    call,
    check_launch,
    promote,
)
from courier_runtime.grants import Broker, Request


class DummyClock:
    t = 2000.0

    def __call__(self):
        return self.t


def make_req(rid, cap="calendar.read", effect="idempotent", res=("cal:work",)):
    return Request(
        request_id=rid,
        project="p1",
        capability=cap,
        resources=frozenset(res),
        host="cloud-1",
        provider_account="acct-1",
        data_class="personal",
        access="read",
        effect_class=effect,
    )


@pytest.fixture
def test_broker():
    b = Broker(DummyClock())
    # Pre-grant calendar.read and calendar.invite
    b.authorize(make_req("r-init-read", cap="calendar.read", effect="idempotent"))
    b.grant(make_req("r-init-read", cap="calendar.read", effect="idempotent"), "g-read", expires_at=None)

    b.authorize(make_req("r-init-invite", cap="calendar.invite", effect="non_idempotent"))
    b.grant(make_req("r-init-invite", cap="calendar.invite", effect="non_idempotent"), "g-invite", expires_at=None)
    return b


SPEC = AdapterSpec(
    "calendar_adapter",
    "2.0",
    {
        "calendar.read": "idempotent",
        "calendar.invite": "non_idempotent",
    },
)

CAMPAIGN_GRANT = CampaignGrant(
    grant_id="cg-100",
    ad_account="acct-corp",
    channel="search",
    creative_hash="hash-cr-1",
    audience_hash="hash-aud-1",
    regions=frozenset({"DE", "AT"}),
    daily_budget_cap=50.0,
    total_budget_cap=1000.0,
    start=100.0,
    end=86400.0 * 20,
    allowed_actions=frozenset({"create", "pause"}),
)


class TestRuntimeAdapterExtended:
    """Rigorous edge-case coverage for provider-neutral adapter dispatch and campaign boundaries."""

    def test_non_idempotent_transient_failure_never_retries(self, test_broker):
        # A non-idempotent operation with a transient failure must NOT be retry-eligible
        req = make_req("r-invite-1", cap="calendar.invite", effect="non_idempotent")
        result = call(SPEC, test_broker, req, lambda q: (False, {"attempt": 1}, "transient"))
        assert result.status == "FAILED"
        assert result.retry_eligible is False
        assert result.evidence == {"attempt": 1}

    def test_unknown_failure_class_falls_back_to_uncertain_effect(self, test_broker):
        req = make_req("r-read-1", cap="calendar.read", effect="idempotent")
        result = call(SPEC, test_broker, req, lambda q: (False, {}, "something_unheard_of"))
        assert result.failure == "uncertain_effect"
        assert result.status == "NEEDS_USER"
        assert result.retry_eligible is False

    def test_promote_preview_max_spend_calculation(self):
        # 10 days duration with 20/day vs 500 total budget -> max_spend is 200
        plan = CampaignPlan(
            ad_account="acct-corp",
            channel="search",
            creative_hash="hash-cr-1",
            audience_hash="hash-aud-1",
            regions=frozenset({"DE", "AT"}),
            daily_budget=20.0,
            total_budget=500.0,
            start=0.0,
            end=86400.0 * 10,
        )
        res = promote(plan)
        assert res["effect"] is None
        assert res["preview"]["regions"] == ["AT", "DE"]  # sorted
        assert res["preview"]["max_spend"] == 200.0

        # High daily budget capped by total budget
        plan_high = replace(plan, daily_budget=100.0)  # 100 * 10 = 1000 > 500 total
        res_high = promote(plan_high)
        assert res_high["preview"]["max_spend"] == 500.0

    def test_check_launch_none_grant_requires_explicit_authority(self):
        plan = CampaignPlan("a", "b", "c", "d", frozenset({"DE"}), 10.0, 100.0, 0.0, 100.0)
        violations = check_launch(plan, None)
        assert len(violations) == 1
        assert "no campaign grant" in violations[0]

    def test_check_launch_pause_action_is_always_narrowing(self):
        # Action "pause" bypasses budget/region constraints as long as "pause" is allowed
        plan = CampaignPlan(
            ad_account="different_acct",
            channel="social",
            creative_hash="c2",
            audience_hash="a2",
            regions=frozenset({"US", "FR"}),
            daily_budget=99999.0,
            total_budget=999999.0,
            start=0.0,
            end=9999999.0,
        )
        violations = check_launch(plan, CAMPAIGN_GRANT, action="pause")
        assert violations == []

    def test_check_launch_all_constraint_violations_accumulated(self):
        # Plan violates ad_account, regions, daily budget, total budget, start/end windows
        bad_plan = CampaignPlan(
            ad_account="hacked_account",
            channel="unauthorized_channel",
            creative_hash="bad_cr",
            audience_hash="bad_aud",
            regions=frozenset({"DE", "CH"}),  # CH not in {DE, AT}
            daily_budget=999.0,               # > 50 cap
            total_budget=5000.0,              # > 1000 cap
            start=10.0,                       # < 100 grant.start
            end=86400.0 * 50,                 # > 86400 * 20 grant.end
        )
        violations = check_launch(bad_plan, CAMPAIGN_GRANT, action="create")
        assert any("ad_account changed" in v for v in violations)
        assert any("channel changed" in v for v in violations)
        assert any("creative_hash changed" in v for v in violations)
        assert any("audience_hash changed" in v for v in violations)
        assert any("regions ['CH'] not granted" in v for v in violations)
        assert any("daily budget above cap" in v for v in violations)
        assert any("total budget above cap" in v for v in violations)
        assert any("duration outside the granted window" in v for v in violations)
        assert len(violations) == 8

    def test_check_launch_unauthorized_action(self):
        plan = CampaignPlan(
            ad_account=CAMPAIGN_GRANT.ad_account,
            channel=CAMPAIGN_GRANT.channel,
            creative_hash=CAMPAIGN_GRANT.creative_hash,
            audience_hash=CAMPAIGN_GRANT.audience_hash,
            regions=CAMPAIGN_GRANT.regions,
            daily_budget=10.0,
            total_budget=100.0,
            start=200.0,
            end=86400.0 * 10,
        )
        # "resume" is not in allowed_actions {"create", "pause"}
        violations = check_launch(plan, CAMPAIGN_GRANT, action="resume")
        assert violations == ["action resume not granted"]
