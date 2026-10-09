"""L2 pins: sealing assigns the chain position and rows round-trip exactly.

``Event.sealed()`` is the only way a position (seq/prev_hash/hash) is
assigned, and ``Event.from_row()`` is the only way stored bytes become an
event again. These tests pin that contract: sealing is deterministic and
non-mutating, a sealed chain links through prev_hash, a stored row restores
every field bit-for-bit, and any edit of the stored bytes is detectable
because the recomputed hash no longer matches the stored one.
"""

import json

from core_builders import Attempt, created
from courier_core.events import GENESIS_HASH, Event, EventType, chain_hash


def _stored_row(event):
    """Mirror what the journal writes: type as value, payload as text."""
    return {
        "type": event.type.value,
        "task_id": event.task_id,
        "attempt": event.attempt,
        "dispatch_id": event.dispatch_id,
        "worker_id": event.worker_id,
        "result_id": event.result_id,
        "payload": event.payload_json,
        "event_id": event.event_id,
        "ts_utc": event.ts_utc,
        "dedupe_key": event.dedupe_key,
        "schema_v": event.schema_v,
        "seq": event.seq,
        "prev_hash": event.prev_hash,
        "hash": event.hash,
    }


def test_sealed_assigns_position_and_hash_without_mutating():
    event = created("t-seal")
    sealed = event.sealed(1, GENESIS_HASH)
    assert sealed.seq == 1
    assert sealed.prev_hash == GENESIS_HASH
    assert sealed.hash == chain_hash(sealed)
    # The frozen original is untouched: only the journal seals, once.
    assert event.seq is None
    assert event.prev_hash is None
    assert event.hash is None
    assert sealed.content() == event.content()


def test_sealed_is_deterministic_for_same_inputs():
    event = created("t-seal-d")
    first = event.sealed(3, "ab" * 32)
    second = event.sealed(3, "ab" * 32)
    assert first.hash == second.hash
    assert first.sealed(4, "ab" * 32).hash != first.hash
    assert first.sealed(3, "cd" * 32).hash != first.hash


def test_sealed_chain_links_through_prev_hash():
    attempt = Attempt("t-chain", 1)
    first = attempt.claimed().sealed(1, GENESIS_HASH)
    second = attempt.started().sealed(2, first.hash)
    assert second.prev_hash == first.hash
    assert second.hash == chain_hash(second)
    assert second.hash != first.hash


def test_from_row_restores_every_stored_field():
    attempt = Attempt("t-row", 1)
    sealed = attempt.result_ready().sealed(7, "ef" * 32)
    restored = Event.from_row(_stored_row(sealed))
    assert restored.type == sealed.type
    assert restored.task_id == sealed.task_id
    assert restored.attempt == sealed.attempt
    assert restored.dispatch_id == sealed.dispatch_id
    assert restored.worker_id == sealed.worker_id
    assert restored.result_id == sealed.result_id
    assert restored.payload == sealed.payload
    assert restored.event_id == sealed.event_id
    assert restored.ts_utc == sealed.ts_utc
    assert restored.dedupe_key == sealed.dedupe_key
    assert restored.schema_v == sealed.schema_v
    assert restored.seq == sealed.seq
    assert restored.prev_hash == sealed.prev_hash
    assert restored.hash == sealed.hash
    assert restored.content() == sealed.content()
    assert chain_hash(restored) == restored.hash


def test_from_row_accepts_string_type_and_recoerces():
    sealed = created("t-row-type").sealed(1, GENESIS_HASH)
    row = _stored_row(sealed)
    assert isinstance(row["type"], str)
    restored = Event.from_row(row)
    assert restored.type is EventType.TASK_CREATED


def test_edited_stored_bytes_fail_hash_verification():
    sealed = created("t-tamper").sealed(1, GENESIS_HASH)
    row = _stored_row(sealed)
    payload = json.loads(row["payload"])
    payload["adapter"] = "edited-adapter"
    row["payload"] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    restored = Event.from_row(row)
    # Construction still succeeds, but the chain check catches the edit:
    # the recomputed hash no longer matches the stored hash.
    assert chain_hash(restored) != restored.hash
    assert chain_hash(restored) != sealed.hash
