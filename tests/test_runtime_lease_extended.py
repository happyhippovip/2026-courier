import pytest
from courier_runtime.lease import LeaseConflict, LeaseStore, StaleLease


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def store(tmp_path):
    clock = Clock()
    s = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    yield s, clock
    s.close()


def test_lease_current_none_when_unheld(store):
    s, _ = store
    assert s.current("nonexistent_scope") is None


def test_lease_check_write_raises_on_expired_token(store):
    s, clock = store
    lease = s.acquire("scope-a", "holder-1", "wk-1", ttl_s=10)
    assert s.check_write("scope-a", lease.token) == lease

    # Expire lease
    clock.t += 11
    with pytest.raises(StaleLease) as exc:
        s.check_write("scope-a", lease.token)
    assert "refused" in str(exc.value)


def test_lease_renew_fails_on_wrong_holder_or_token(store):
    s, clock = store
    lease = s.acquire("scope-b", "holder-1", "wk-1", ttl_s=20)

    # Fake lease with wrong token
    bad_token_lease = type(lease)(lease.scope, lease.holder, lease.workkey, lease.token + 99, lease.expires_at)
    with pytest.raises(StaleLease):
        s.renew(bad_token_lease, ttl_s=20)

    # Fake lease with wrong holder
    bad_holder_lease = type(lease)(lease.scope, "imposter", lease.workkey, lease.token, lease.expires_at)
    with pytest.raises(StaleLease):
        s.renew(bad_holder_lease, ttl_s=20)


def test_lease_release_idempotency_and_no_effect_on_mismatch(store):
    s, clock = store
    lease = s.acquire("scope-c", "holder-1", "wk-1", ttl_s=20)

    # Mismatched holder release does nothing
    bad_lease = type(lease)(lease.scope, "imposter", lease.workkey, lease.token, lease.expires_at)
    s.release(bad_lease)
    assert s.current("scope-c") is not None

    # Proper release
    s.release(lease)
    assert s.current("scope-c") is None

    # Second release does not fail
    s.release(lease)
    assert s.current("scope-c") is None
