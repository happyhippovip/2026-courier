from dataclasses import replace

import pytest

from courier_runtime.grants import (DENIED, GRANTED, REQUESTED, WAITING_FOR_OS_PERMISSION,
                                    WAITING_FOR_USER_PERMISSION, Broker, Request, TransitionError)


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


# -- permission broker ----------------------------------------------------------

def req(rid="r1", **kw):
    base = dict(request_id=rid, project="p1", capability="network.read",
                resources=frozenset({"api.github.com:443"}), host="win-1", provider_account="",
                data_class="public", access="read", effect_class="idempotent")
    base.update(kw)
    return Request(**base)


@pytest.fixture
def broker():
    clock = Clock()
    return Broker(clock), clock


def test_ask_once_then_reuse(broker):
    b, _ = broker
    grant, state, _ = b.authorize(req("r1"))
    assert (grant, state) == (None, REQUESTED)
    b.move("r1", WAITING_FOR_USER_PERMISSION)
    b.grant(req("r1"), "g1", expires_at=2000)
    grant, state, _ = b.authorize(req("r2"))
    assert state == GRANTED and grant.grant_id == "g1"
    assert [e["type"] for e in b.events].count("GRANT_REQUESTED") == 1


@pytest.mark.parametrize("wider", [
    dict(resources=frozenset({"api.github.com:443", "evil.example:443"})),
    dict(resources=frozenset({"uploads.github.com:443"})),
    dict(access="write"),
    dict(data_class="personal"),
    dict(project="p2"),
    dict(host="mac-1"),
    dict(provider_account="acct-2"),
    dict(capability="fs.write"),
    dict(effect_class="non_idempotent"),
])
def test_any_wider_dimension_is_not_covered(broker, wider):
    b, _ = broker
    b.authorize(req("r1"))
    b.grant(req("r1"), "g1", expires_at=2000)
    grant, state, reason = b.authorize(req("r2", **wider))
    assert grant is None and state == REQUESTED and reason


def test_expiry_and_revocation_stop_reuse(broker):
    b, clock = broker
    b.authorize(req("r1"))
    b.grant(req("r1"), "g1", expires_at=1500)
    clock.t = 1500
    assert b.authorize(req("r2"))[1] == REQUESTED
    b.expire_due()
    assert b.grants["g1"].state == "EXPIRED"
    b.grant(req("r2"), "g2", expires_at=None)
    b.revoke("g2")
    assert b.authorize(req("r3"))[1] == REQUESTED


def test_one_time_grant_is_used_once(broker):
    b, _ = broker
    b.authorize(req("r1"))
    b.grant(req("r1"), "g1", expires_at=2000, once=True)
    assert b.authorize(req("r2"))[1] == GRANTED
    assert b.authorize(req("r3"))[1] == REQUESTED


def test_os_wait_never_auto_grants_and_illegal_transitions_fail(broker):
    b, _ = broker
    b.authorize(req("r1"))
    b.move("r1", WAITING_FOR_OS_PERMISSION)
    assert b.requests["r1"] == WAITING_FOR_OS_PERMISSION and not b.grants
    b.deny("r1")
    assert b.requests["r1"] == DENIED
    with pytest.raises(TransitionError):
        b.grant(req("r1"), "g1", expires_at=2000)
    with pytest.raises(TransitionError):
        b.move("r1", WAITING_FOR_USER_PERMISSION)


def test_grant_records_exactly_the_requested_scope(broker):
    b, _ = broker
    b.authorize(req("r1"))
    g = b.grant(req("r1"), "g1", expires_at=2000)
    assert g.resources == frozenset({"api.github.com:443"}) and g.access == "read"
    assert g.source_request == "r1" and g.granted_by == "user"
    assert replace(g, uses=0) == replace(b.grants["g1"], uses=0)
