"""L2 invariants: event validation, canonical encoding and default dedupe keys."""

import math

import pytest

from core_builders import SHA, Attempt, created
from courier_core.events import (
    GENESIS_HASH, Event, EventType, EventValidationError, canonical_json, chain_hash,
)


def test_golden_events_are_valid_and_get_default_dedupe_keys():
    a = Attempt("t1", 1)
    assert created("t1").dedupe_key == "created:t1"
    assert a.claimed().dedupe_key == "claim:t1:1"
    assert a.started().dedupe_key == f"start:{a.dispatch_id}"
    assert a.result_ready().dedupe_key == f"result:{a.dispatch_id}:{a.result_id}"
    assert a.accepted().dedupe_key == "accepted:t1"
    assert a.complete().dedupe_key == "complete:t1"
    assert a.lease_expired().dedupe_key == f"lease_expired:{a.dispatch_id}"
    assert a.progress().dedupe_key is None


def test_payload_is_a_canonical_copy():
    params = {"b": 1, "a": [1, 2]}
    event = Event(type=EventType.TASK_CREATED, task_id="t", payload={
        "adapter": "synthetic", "params": params, "effect_class": "idempotent",
        "max_attempts": 1, "lease_ttl_s": 5})
    params["b"] = 99
    assert event.payload["params"] == {"a": [1, 2], "b": 1}
    assert event.payload_json == canonical_json(event.payload)
    assert event.payload_json.index('"adapter"') < event.payload_json.index('"params"')


@pytest.mark.parametrize("kwargs, message", [
    (dict(type="NOT_A_TYPE", task_id="t"), "unknown event type"),
    (dict(type=EventType.TASK_STARTED, task_id="t", attempt=1, worker_id="w"), "requires dispatch_id"),
    (dict(type=EventType.TASK_STARTED, task_id="t", attempt=True, dispatch_id="d", worker_id="w"), "attempt"),
    (dict(type=EventType.TASK_STARTED, task_id="t", attempt=0, dispatch_id="d", worker_id="w"), "attempt"),
    (dict(type=EventType.TASK_STARTED, task_id="", attempt=1, dispatch_id="d", worker_id="w"), "task_id"),
    (dict(type=EventType.TASK_STARTED, task_id="t" * 201, attempt=1, dispatch_id="d", worker_id="w"), "task_id"),
    (dict(type=EventType.CONTROLLER_STARTED, task_id="t"), "system event"),
    (dict(type=EventType.TASK_CANCELLED, task_id="t", ts_utc="2026-10-01T00:00:00+02:00"), "ts_utc"),
    (dict(type=EventType.TASK_CANCELLED, task_id="t", payload={"x": math.nan}), "canonical JSON"),
    (dict(type=EventType.TASK_CANCELLED, task_id="t", payload=["not", "an", "object"]), "JSON object"),
    (dict(type=EventType.TASK_CREATED, task_id="t", payload={"adapter": "s", "params": {}}), "payload requires"),
    (dict(type=EventType.TASK_CREATED, task_id="t", payload={
        "adapter": "s", "params": {}, "effect_class": "maybe", "max_attempts": 1, "lease_ttl_s": 5}), "effect_class"),
    (dict(type=EventType.TASK_CREATED, task_id="t", payload={
        "adapter": "s", "params": {}, "effect_class": "idempotent", "max_attempts": 0, "lease_ttl_s": 5}),
     "max_attempts"),
    (dict(type=EventType.LEASE_EXPIRED, task_id="t", attempt=1, dispatch_id="d", worker_id="w",
          payload={"reason": "because"}), "lease expiry reason"),
    (dict(type=EventType.RESULT_READY, task_id="t", attempt=1, dispatch_id="d", worker_id="w", result_id="r",
          payload={"artifacts": [{"path": "o", "sha256": "ABC"}], "outcome": "success"}), "sha256"),
    (dict(type=EventType.RESULT_READY, task_id="t", attempt=1, dispatch_id="d", worker_id="w", result_id="r",
          payload={"artifacts": [], "outcome": "maybe"}), "outcome"),
    (dict(type=EventType.RESULT_REJECTED, task_id="t", attempt=1, dispatch_id="d", result_id="r",
          payload={"reason": "x", "retryable": "yes"}), "retryable"),
])
def test_malformed_events_never_construct(kwargs, message):
    with pytest.raises(EventValidationError, match=message):
        Event(**kwargs)


def test_chain_hash_covers_every_stored_field():
    base = Attempt("t1", 1).result_ready().sealed(1, GENESIS_HASH)
    assert base.hash == chain_hash(base)
    variants = [
        base.sealed(2, GENESIS_HASH),
        base.sealed(1, "1" * 64),
        Attempt("t1", 1).result_ready(sha="0" * 64).sealed(1, GENESIS_HASH),
    ]
    assert len({base.hash, *(v.hash for v in variants)}) == 4
    assert chain_hash(base, payload_text=base.payload_json + " ") != base.hash


def test_content_ignores_identity_and_time_only():
    a, b = Attempt("t1", 1).result_ready(), Attempt("t1", 1).result_ready()
    assert a.event_id != b.event_id and a.ts_utc != b.ts_utc
    assert a.content() == b.content()
    assert a.content() != Attempt("t1", 1).result_ready(sha="1" * 64).content()
    assert SHA in a.payload_json
