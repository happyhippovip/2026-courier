from dataclasses import FrozenInstanceError
import pytest
from courier_runtime.lease import Lease, LeaseConflict, LeaseStore, StaleLease

class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

@pytest.fixture
def lease_env(tmp_path):
    clock = Clock(5000.0)
    store = LeaseStore(str(tmp_path / "lease_edge.db"), clock=clock)
    yield store, clock
    store.close()

def test_lease_dataclass_immutable():
    lease = Lease(scope="s", holder="h", workkey="w", token=1, expires_at=100.0)
    with pytest.raises(FrozenInstanceError):
        lease.token = 2
    with pytest.raises(FrozenInstanceError):
        lease.expires_at = 200.0

def test_check_write_on_missing_scope_raises_stale(lease_env):
    store, _ = lease_env
    with pytest.raises(StaleLease, match="write to missing:scope with token 1 refused"):
        store.check_write("missing:scope", 1)

def test_check_write_exact_expiration_fencing(lease_env):
    store, clock = lease_env
    lease = store.acquire("scope:fence", "node1", "wk-1", ttl_s=10)
    # At exact expiration (now == expires_at), current() returns None (requires expires_at > now)
    clock.t += 10.0
    with pytest.raises(StaleLease):
        store.check_write("scope:fence", lease.token)

def test_reacquire_after_expiration_bumps_token(lease_env):
    store, clock = lease_env
    first = store.acquire("scope:bump", "node1", "wk-1", ttl_s=10)
    assert first.token == 1
    # Expire the lease
    clock.t += 15.0
    # Re-acquire by same holder
    second = store.acquire("scope:bump", "node1", "wk-1", ttl_s=10)
    # Token must have been bumped because it expired
    assert second.token == 2
    # Old token is stale
    with pytest.raises(StaleLease):
        store.check_write("scope:bump", first.token)
    # New token is valid
    assert store.check_write("scope:bump", second.token).holder == "node1"

def test_release_by_impostor_is_ignored(lease_env):
    store, _ = lease_env
    legit = store.acquire("scope:protect", "node1", "wk-1", ttl_s=60)
    # Impostor tries to release with wrong holder
    impostor = Lease(scope=legit.scope, holder="bad-node", workkey=legit.workkey, token=legit.token, expires_at=legit.expires_at)
    store.release(impostor)
    # Legitimate lease is still active
    assert store.current("scope:protect") is not None
    assert store.current("scope:protect").holder == "node1"
    
    # Impostor tries to release with wrong token
    wrong_token = Lease(scope=legit.scope, holder=legit.holder, workkey=legit.workkey, token=999, expires_at=legit.expires_at)
    store.release(wrong_token)
    assert store.current("scope:protect") is not None

def test_renew_with_wrong_holder_or_token_raises_stale(lease_env):
    store, _ = lease_env
    lease = store.acquire("scope:renew", "node1", "wk-1", ttl_s=60)
    
    bad_holder = Lease(scope=lease.scope, holder="other", workkey=lease.workkey, token=lease.token, expires_at=lease.expires_at)
    with pytest.raises(StaleLease):
        store.renew(bad_holder, ttl_s=60)
        
    bad_token = Lease(scope=lease.scope, holder=lease.holder, workkey=lease.workkey, token=lease.token + 5, expires_at=lease.expires_at)
    with pytest.raises(StaleLease):
        store.renew(bad_token, ttl_s=60)

def test_multiple_independent_scopes_concurrency(lease_env):
    store, _ = lease_env
    scopes = [f"scope:{i}" for i in range(5)]
    leases = [store.acquire(s, f"node-{i}", f"wk-{i}", ttl_s=30) for i, s in enumerate(scopes)]
    
    for i, s in enumerate(scopes):
        current = store.current(s)
        assert current is not None
        assert current.holder == f"node-{i}"
        assert store.check_write(s, leases[i].token).holder == f"node-{i}"
