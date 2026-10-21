import concurrent.futures
import pytest

from courier_runtime.lease import Lease, LeaseConflict, LeaseStore, StaleLease


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


def test_invalid_parameters_fail_closed(leases):
    """Beweis (S08): Input-Validierung stellt sicher, dass ungueltige Parameter fail-closed abgewiesen werden."""
    store, _ = leases

    # Ungueltiges Scope
    for bad_scope in ("", "   ", None, 123):
        with pytest.raises(ValueError):
            store.acquire(bad_scope, "h", "wk", 10)

    # Ungueltiger Holder
    for bad_holder in ("", "   ", None, ["h"]):
        with pytest.raises(ValueError):
            store.acquire("scope", bad_holder, "wk", 10)

    # Ungueltiger Workkey
    for bad_workkey in ("", "   ", None, {"w": 1}):
        with pytest.raises(ValueError):
            store.acquire("scope", "h", bad_workkey, 10)

    # Ungueltige TTL (0, negativ, NaN, Inf, Bool, String)
    for bad_ttl in (0, -1, -0.1, float("nan"), float("inf"), float("-inf"), True, False, "30"):
        with pytest.raises(ValueError):
            store.acquire("scope", "h", "wk", bad_ttl)


def test_check_write_rejects_invalid_tokens_and_stale_tokens(leases):
    """Beweis (S08): Fencing verweigert nicht-ganzzahlige, negative oder veraltete Fencing-Tokens."""
    store, _ = leases
    lease = store.acquire("scope", "h", "wk", 30)

    # Gueltiger Token akzeptiert
    assert store.check_write("scope", lease.token).holder == "h"

    # Ungueltige Token-Typen abgewiesen
    for bad_token in (0, -1, -99, "1", None, True, False, 1.5):
        with pytest.raises(StaleLease):
            store.check_write("scope", bad_token)

    # Stale Token abgewiesen
    with pytest.raises(StaleLease):
        store.check_write("scope", lease.token + 1)


def test_strict_token_monotonicity_across_lifecycle(leases):
    """Beweis (S08): Fencing-Tokens steigen ueber beliebige Lease-Uebernahmen und Releases streng monoton."""
    store, clock = leases
    tokens = []

    # 1. Erster Erwerb
    l1 = store.acquire("repo:lane", "worker-1", "wk-1", 10)
    tokens.append(l1.token)

    # 2. Gleicher Holder verlaengert -> Token bleibt identisch
    clock.t += 5
    l1_renewed = store.renew(l1, 10)
    assert l1_renewed.token == l1.token

    # 3. Release und Neuerwerb durch worker-2 -> Token steigt
    store.release(l1_renewed)
    l2 = store.acquire("repo:lane", "worker-2", "wk-2", 10)
    tokens.append(l2.token)

    # 4. Ablauf (Expiry) und Uebernahme durch worker-3 -> Token steigt
    clock.t += 15
    l3 = store.acquire("repo:lane", "worker-3", "wk-3", 10)
    tokens.append(l3.token)

    # 5. Ablauf und Uebernahme durch worker-4 -> Token steigt
    clock.t += 15
    l4 = store.acquire("repo:lane", "worker-4", "wk-4", 10)
    tokens.append(l4.token)

    assert tokens == [1, 2, 3, 4]
    # Alle vorherigen Token sind nun gefenced
    for old_tok in (1, 2, 3):
        with pytest.raises(StaleLease):
            store.check_write("repo:lane", old_tok)
    assert store.check_write("repo:lane", 4).holder == "worker-4"


def test_stale_release_does_not_evict_active_holder(leases):
    """Beweis (S08): Ein veralteter Holder, dessen Lease abgelaufen ist, kann die neue Lease des Nachfolgers nicht loeschen."""
    store, clock = leases

    # Holder A erwirbt
    lease_a = store.acquire("scope", "holder-a", "wk-a", 10)
    clock.t += 15  # Lease A laeuft ab

    # Holder B uebernimmt
    lease_b = store.acquire("scope", "holder-b", "wk-b", 10)
    assert lease_b.token == lease_a.token + 1

    # Holder A versucht verspaetet release() aufzurufen
    store.release(lease_a)

    # Holder B's Lease muss voellig unberuehrt und aktiv bleiben
    current = store.current("scope")
    assert current is not None
    assert current.holder == "holder-b"
    assert current.token == lease_b.token
    assert store.check_write("scope", lease_b.token).holder == "holder-b"


def test_concurrent_threads_atomic_acquire(tmp_path):
    """Beweis (S08): Parallele Threads auf demselben Scope serialisieren atomar. Genau einer gewinnt."""
    db_path = str(tmp_path / "concurrent_lease.db")
    results = []

    def worker_attempt(idx):
        store = LeaseStore(db_path)
        try:
            l = store.acquire("shared-scope", f"thread-{idx}", f"wk-{idx}", 30)
            return ("SUCCESS", idx, l.token)
        except LeaseConflict:
            return ("CONFLICT", idx, None)
        finally:
            store.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(worker_attempt, i) for i in range(8)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[0] == "SUCCESS"]
    conflicts = [r for r in results if r[0] == "CONFLICT"]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == 7, f"Expected 7 conflicts, got {len(conflicts)}"
    assert successes[0][2] == 1, "Winning token must be 1"
