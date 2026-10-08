import pytest
from courier_runtime.grants import (
    Broker, Request, Grant,
    REQUESTED, WAITING_FOR_USER_PERMISSION, WAITING_FOR_OS_PERMISSION,
    GRANTED, DENIED, EXPIRED, REVOKED, TransitionError
)


class MockClock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def make_request(rid="req-1", **kw):
    base = dict(
        request_id=rid,
        project="alpha",
        capability="fs.read",
        resources=frozenset({"/workspace/data.csv"}),
        host="host-mac",
        provider_account="account-01",
        data_class="project",
        access="read",
        effect_class="idempotent"
    )
    base.update(kw)
    return Request(**base)


def test_invalid_state_transitions():
    clock = MockClock()
    b = Broker(clock)
    r = make_request("r-trans")
    b.authorize(r)

    # Cannot transition directly from REQUESTED to EXPIRED
    with pytest.raises(TransitionError):
        b.move("r-trans", EXPIRED)

    # Valid transition to WAITING_FOR_USER_PERMISSION
    b.move("r-trans", WAITING_FOR_USER_PERMISSION)

    # Cannot jump back to REQUESTED
    with pytest.raises(TransitionError):
        b.move("r-trans", REQUESTED)


def test_one_time_grant_usage_limit():
    clock = MockClock()
    b = Broker(clock)
    r = make_request("r-once")
    b.authorize(r)
    b.grant(r, "grant-once", expires_at=2000.0, once=True)

    # First authorization consumes the one-time grant
    g1, st1, _ = b.authorize(make_request("r-use-1"))
    assert st1 == GRANTED
    assert g1.grant_id == "grant-once"

    # Second authorization fails because once=True and uses >= 1
    g2, st2, reason = b.authorize(make_request("r-use-2"))
    assert g2 is None
    assert st2 == REQUESTED
    assert "one-time grant already used" in reason


def test_multi_resource_grant_subset_matching():
    clock = MockClock()
    b = Broker(clock)
    full_req = make_request(
        "r-full",
        resources=frozenset({"/workspace/file1.txt", "/workspace/file2.txt", "/workspace/file3.txt"})
    )
    b.authorize(full_req)
    b.grant(full_req, "grant-multi", expires_at=5000.0)

    # Subset request is covered
    sub_req = make_request("r-sub", resources=frozenset({"/workspace/file1.txt"}))
    g, st, _ = b.authorize(sub_req)
    assert st == GRANTED
    assert g.grant_id == "grant-multi"

    # Superset request is NOT covered
    super_req = make_request(
        "r-super",
        resources=frozenset({"/workspace/file1.txt", "/workspace/file4.txt"})
    )
    g_sup, st_sup, reason = b.authorize(super_req)
    assert g_sup is None
    assert st_sup == REQUESTED
    assert "/workspace/file4.txt" in reason


def test_revoke_active_grant_stops_future_access():
    clock = MockClock()
    b = Broker(clock)
    r = make_request("r-rev")
    b.authorize(r)
    b.grant(r, "g-active", expires_at=3000.0)

    # Active
    assert b.authorize(make_request("r-check-1"))[1] == GRANTED

    # Revoke
    b.revoke("g-active")
    assert b.grants["g-active"].state == REVOKED

    # Future access denied
    g_after, st_after, reason = b.authorize(make_request("r-check-2"))
    assert g_after is None
    assert st_after == REQUESTED
    assert "grant is REVOKED" in reason
