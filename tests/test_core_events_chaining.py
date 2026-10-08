import math
import pytest

from courier_core.events import (
    GENESIS_HASH,
    EventType,
    Event,
    EventValidationError,
    effect_key,
    canonical_json,
    chain_hash,
    default_dedupe_key,
)


def test_effect_key_invariants():
    k1 = effect_key("task-alpha")
    k2 = effect_key("task-alpha")
    k3 = effect_key("task-beta")

    # Determinism
    assert k1 == k2
    assert k1 != k3

    # Format & length: prefix "cfx-" + 40 hex chars = 44 chars
    assert k1.startswith("cfx-")
    assert len(k1) == 44
    hex_part = k1[4:]
    assert all(c in "0123456789abcdef" for c in hex_part)


def test_canonical_json_formatting_and_rejections():
    data = {"zebra": 100, "apple": [3, 2, 1], "banana": {"key2": "val", "key1": "val"}}
    encoded = canonical_json(data)

    # Lexicographical key ordering & no whitespaces after separators
    assert encoded == '{"apple":[3,2,1],"banana":{"key1":"val","key2":"val"},"zebra":100}'

    # Unicode preservation without \u escaping
    unicode_data = {"city": "München", "currency": "€"}
    assert canonical_json(unicode_data) == '{"city":"München","currency":"€"}'

    # Rejection of float NaN and Infs
    with pytest.raises(ValueError):
        canonical_json({"score": float("nan")})
    with pytest.raises(ValueError):
        canonical_json({"score": float("inf")})
    with pytest.raises(ValueError):
        canonical_json({"score": float("-inf")})


def test_chain_hash_and_sealed_integrity():
    event = Event(
        type=EventType.TASK_CREATED,
        task_id="task-123",
        payload={
            "adapter": "synthetic",
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 60,
            "params": {"run": True},
        },
    )

    # Unsealed event has seq=None, prev_hash=None, hash=None
    assert event.seq is None
    assert event.prev_hash is None
    assert event.hash is None

    # Sealing produces deterministic hash chain
    sealed = event.sealed(seq=1, prev_hash=GENESIS_HASH)
    assert sealed.seq == 1
    assert sealed.prev_hash == GENESIS_HASH
    assert sealed.hash is not None
    assert len(sealed.hash) == 64

    # Verification: chain_hash recalculation matches sealed.hash
    calculated = chain_hash(sealed)
    assert calculated == sealed.hash

    # Tampering test: altering payload_text detects modification
    tampered_hash = chain_hash(sealed, payload_text='{"tampered":true}')
    assert tampered_hash != sealed.hash


def test_default_dedupe_key_invariants():
    # TASK_CREATED
    assert default_dedupe_key(EventType.TASK_CREATED, "t1", None, None, None) == "created:t1"

    # TASK_CLAIMED
    assert default_dedupe_key(EventType.TASK_CLAIMED, "t1", 1, None, None) == "claim:t1:1"

    # TASK_STARTED
    assert default_dedupe_key(EventType.TASK_STARTED, "t1", 1, "disp-99", None) == "start:disp-99"

    # TASK_PROGRESS is never deduped
    assert default_dedupe_key(EventType.TASK_PROGRESS, "t1", 1, "disp-99", None) is None

    # RESULT_READY
    assert default_dedupe_key(EventType.RESULT_READY, "t1", 1, "disp-99", "res-01") == "result:disp-99:res-01"

    # RESULT_ACCEPTED
    assert default_dedupe_key(EventType.RESULT_ACCEPTED, "t1", None, None, None) == "accepted:t1"

    # TASK_COMPLETE
    assert default_dedupe_key(EventType.TASK_COMPLETE, "t1", None, None, None) == "complete:t1"

    # LEASE_EXPIRED
    assert default_dedupe_key(EventType.LEASE_EXPIRED, "t1", 1, "disp-99", None) == "lease_expired:disp-99"


def test_event_from_row_reconstruction():
    row = {
        "type": "TASK_CREATED",
        "task_id": "task-row-1",
        "attempt": None,
        "dispatch_id": None,
        "worker_id": None,
        "result_id": None,
        "payload": '{"adapter":"synthetic","effect_class":"idempotent","max_attempts":1,"lease_ttl_s":10,"params":{}}',
        "event_id": "evt-row-1",
        "ts_utc": "2026-10-08T12:00:00.000000Z",
        "dedupe_key": "created:task-row-1",
        "schema_v": 1,
        "seq": 10,
        "prev_hash": GENESIS_HASH,
        "hash": "a" * 64,
    }

    event = Event.from_row(row)
    assert event.type == EventType.TASK_CREATED
    assert event.task_id == "task-row-1"
    assert event.seq == 10
    assert event.prev_hash == GENESIS_HASH
    assert event.hash == "a" * 64
    assert event.payload["adapter"] == "synthetic"
