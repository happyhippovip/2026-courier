import pytest

from courier_core.worker_tokens import TokenStore

NOW = 10_000.0


def test_mint_then_verify_round_trips():
    store = TokenStore()
    token, record = store.mint("w1", ("read", "write"), ttl_seconds=60, now=NOW)
    assert token.startswith("cwt_")
    assert store.verify(token, now=NOW) == record


def test_unknown_token_fails_closed():
    store = TokenStore()
    token, _ = store.mint("w1", ("read",), now=NOW)
    assert store.verify(token + "x", now=NOW) is None
    assert store.verify("", now=NOW) is None
    assert store.verify(None, now=NOW) is None


def test_expired_token_is_rejected():
    store = TokenStore()
    token, _ = store.mint("w1", ("read",), ttl_seconds=60, now=NOW)
    assert store.verify(token, now=NOW + 61) is None


def test_out_of_scope_is_rejected():
    store = TokenStore()
    token, _ = store.mint("w1", ("read",), now=NOW)
    assert store.verify(token, "write", now=NOW) is None
    assert store.verify(token, "read", now=NOW) is not None


def test_revoked_token_is_rejected():
    store = TokenStore()
    token, record = store.mint("w1", ("read",), now=NOW)
    assert store.revoke(record.token_id) is True
    assert store.verify(token, now=NOW) is None
    assert store.revoke(record.token_id) is False
    assert store.revoke("no-such-id") is False


def test_stored_record_never_contains_token_value():
    store = TokenStore()
    token, record = store.mint("w1", ("read",), now=NOW)
    assert token not in repr(record)
    assert token not in (record.token_id, record.salt, record.token_hash)
    assert store.get(record.token_id) == record


def test_two_mints_differ_by_salt():
    store = TokenStore()
    t1, r1 = store.mint("w1", ("read",), now=NOW)
    t2, r2 = store.mint("w1", ("read",), now=NOW)
    assert t1 != t2
    assert (r1.salt, r1.token_hash) != (r2.salt, r2.token_hash)
    assert store.verify(t1, now=NOW) == r1
    assert store.verify(t2, now=NOW) == r2


def test_purge_expired_drops_only_expired():
    store = TokenStore()
    _, r1 = store.mint("w1", ("read",), ttl_seconds=60, now=NOW)
    _, r2 = store.mint("w2", ("read",), ttl_seconds=3600, now=NOW)
    assert store.purge_expired(now=NOW + 61) == 1
    assert store.get(r1.token_id) is None
    assert store.get(r2.token_id) == r2


def test_mint_rejects_bad_input():
    store = TokenStore()
    with pytest.raises(ValueError):
        store.mint("", ("read",))
    with pytest.raises(ValueError):
        store.mint("w1", ("read",), ttl_seconds=0)
