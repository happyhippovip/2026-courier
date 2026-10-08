import pytest
from courier_runtime.grants import (
    Broker,
    Grant,
    Request,
    why_not_covered,
    ACCESS_ORDER,
    DATA_ORDER,
    GRANTED,
    REVOKED,
    EXPIRED,
    DENIED,
    REQUESTED,
    WAITING_FOR_USER_PERMISSION,
    WAITING_FOR_OS_PERMISSION,
    TransitionError,
)


class Clock:
    def __init__(self, t=100.0):
        self.t = t

    def __call__(self):
        return self.t


def test_access_and_data_order():
    assert ACCESS_ORDER["read"] < ACCESS_ORDER["write"] < ACCESS_ORDER["execute"] < ACCESS_ORDER["control"]
    assert DATA_ORDER["public"] < DATA_ORDER["project"] < DATA_ORDER["personal"]


def test_why_not_covered_reasons():
    grant = Grant(
        grant_id="g1",
        project="p1",
        capability="net",
        resources=frozenset({"example.com"}),
        host="host-1",
        provider_account="",
        data_class="public",
        access="read",
        effect_class="safe",
        expires_at=200.0,
        once=False,
    )

    # Empty resources
    req_empty = Request("r0", "p1", "net", frozenset(), "host-1", "", "public", "read", "safe")
    assert "resources [] not granted" in why_not_covered(grant, req_empty, 100.0)

    # State not GRANTED
    revoked_grant = Grant(
        grant_id="g1",
        project="p1",
        capability="net",
        resources=frozenset({"example.com"}),
        host="host-1",
        provider_account="",
        data_class="public",
        access="read",
        effect_class="safe",
        expires_at=200.0,
        state=REVOKED,
    )
    req = Request("r1", "p1", "net", frozenset({"example.com"}), "host-1", "", "public", "read", "safe")
    assert why_not_covered(revoked_grant, req, 100.0) == "grant is REVOKED"


def test_broker_waiting_for_os_permission_to_user_permission():
    clock = Clock()
    broker = Broker(clock)
    req = Request("r1", "p1", "net", frozenset({"example.com"}), "host-1", "", "public", "read", "safe")

    broker.authorize(req)
    assert broker.requests["r1"] == REQUESTED

    # Can move REQUESTED -> WAITING_FOR_OS_PERMISSION
    broker.move("r1", WAITING_FOR_OS_PERMISSION)
    assert broker.requests["r1"] == WAITING_FOR_OS_PERMISSION

    # Can move WAITING_FOR_OS_PERMISSION -> WAITING_FOR_USER_PERMISSION
    broker.move("r1", WAITING_FOR_USER_PERMISSION)
    assert broker.requests["r1"] == WAITING_FOR_USER_PERMISSION

    # And then grant it
    g = broker.grant(req, "g1", expires_at=500.0)
    assert broker.requests["r1"] == GRANTED
    assert g.grant_id == "g1"


def test_broker_illegal_revoke():
    clock = Clock()
    broker = Broker(clock)
    req = Request("r1", "p1", "net", frozenset({"example.com"}), "host-1", "", "public", "read", "safe")
    broker.authorize(req)
    broker.grant(req, "g1", expires_at=500.0)

    broker.revoke("g1")
    assert broker.grants["g1"].state == REVOKED

    # Revoking already REVOKED grant raises TransitionError
    with pytest.raises(TransitionError):
        broker.revoke("g1")
