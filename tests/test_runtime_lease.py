import pytest

from courier_runtime.lease import LeaseConflict, LeaseStore, StaleLease


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


# -- work lease ---------------------------------------------------------------

@pytest.fixture
def leases(tmp_path):
    clock = Clock()
    store = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    yield store, clock
    store.close()


def test_one_active_write_lease_per_scope(leases):
    store, _ = leases
    store.acquire("repo:integration/v1", "mac:s1", "wk-1", ttl_s=30)
    with pytest.raises(LeaseConflict):
        store.acquire("repo:integration/v1", "win:s2", "wk-2", ttl_s=30)
    assert store.acquire("repo:other", "win:s2", "wk-2", ttl_s=30).token == 1


def test_expired_lease_can_be_taken_over_and_old_holder_is_fenced(leases):
    store, clock = leases
    old = store.acquire("scope", "mac:s1", "wk-1", ttl_s=30)
    clock.t += 31
    new = store.acquire("scope", "win:s2", "wk-1", ttl_s=30)
    assert new.token == old.token + 1
    with pytest.raises(StaleLease):
        store.check_write("scope", old.token)       # a still-running old holder cannot write
    with pytest.raises(StaleLease):
        store.renew(old, ttl_s=30)                  # nor heartbeat its way back
    assert store.check_write("scope", new.token).holder == "win:s2"


def test_heartbeat_extends_and_same_holder_reacquire_keeps_token(leases):
    store, clock = leases
    lease = store.acquire("scope", "h", "wk", ttl_s=10)
    clock.t += 8
    lease = store.renew(lease, ttl_s=10)
    clock.t += 8
    assert store.current("scope") is not None
    assert store.acquire("scope", "h", "wk", ttl_s=10).token == lease.token


def test_release_frees_scope_but_token_keeps_increasing(leases):
    store, _ = leases
    first = store.acquire("scope", "a", "wk", ttl_s=10)
    store.release(first)
    assert store.current("scope") is None
    assert store.acquire("scope", "b", "wk", ttl_s=10).token == first.token + 1


def test_two_connections_see_the_same_lease(tmp_path):
    clock = Clock()
    a = LeaseStore(str(tmp_path / "l.db"), clock=clock)
    b = LeaseStore(str(tmp_path / "l.db"), clock=clock)
    a.acquire("scope", "a", "wk", ttl_s=10)
    with pytest.raises(LeaseConflict):
        b.acquire("scope", "b", "wk", ttl_s=10)
    a.close()
    b.close()
