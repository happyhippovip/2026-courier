"""O7-04 (B2 Single Writer): a writer lease without an owner id must be refused.

courier_runtime/lease.py:73-75 defines holder_ok() (non-empty str, no bool), but
LeaseStore.acquire (lease.py:125-170) never calls it. A lease is granted with a
fencing token to holder "", None, True or 0. With holder=None the row is stored with
holder NULL, so current() reports the scope as free (lease.py:121) while the caller
holds a token: a second writer can take the same scope.
Guard (holds): the Windows daemon refuses an empty worker id before any lock
(scripts/windows_worker/daemon.py:534-541).
"""
import pytest

from courier_runtime.lease import LeaseStore
from tests.test_windows_costgate_and_writer_lease import load_daemon


def _store(tmp_path):
    return LeaseStore(str(tmp_path / "lease.db"), clock=lambda: 1000.0)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-04/B2: LeaseStore.acquire grants a lease without an owner id")
@pytest.mark.parametrize("holder", ["", None, True, 0])
def test_lease_without_owner_id_is_refused(tmp_path, holder):
    store = _store(tmp_path)
    try:
        try:
            lease = store.acquire("repo:courier-v1", holder, "wk-1", ttl_s=30)
        except Exception:
            return  # expected after a fix: refused, no token handed out
        raise AssertionError(f"lease granted to holder {holder!r} with token {lease.token}")
    finally:
        store.close()


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-04/B2: an owner-less (NULL) lease lets a second writer into the same scope")
def test_ownerless_lease_does_not_let_a_second_writer_in(tmp_path):
    store = _store(tmp_path)
    try:
        ghost = None
        try:
            ghost = store.acquire("repo:courier-v1", None, "wk-1", ttl_s=30)
        except Exception:
            pass
        second = None
        try:
            second = store.acquire("repo:courier-v1", "win-worker-02", "wk-2", ttl_s=30)
        except Exception:
            pass
        assert not (ghost is not None and second is not None), (ghost, second)
    finally:
        store.close()


@pytest.mark.parametrize("worker_id", ["", None])
def test_guard_daemon_refuses_empty_worker_id(tmp_path, monkeypatch, worker_id):
    daemon = load_daemon(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        daemon.acquire_lock(worker_id)
