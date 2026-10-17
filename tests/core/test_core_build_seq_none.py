"""P9 hardening for courier_core.build: None-seq + missing-build pins.

Tests only; no behavior change. No network calls.

Focus: build_for_seq() attribution edges that are easy to misread:
- unsealed events (seq None) never trigger the early break;
- a CONTROLLER_STARTED without a "build" key resets attribution to None;
- empty streams, late STARTED events, and generator inputs.
"""

from courier_core.build import build_for_seq
from courier_core.events import Event, EventType


def _started(seq, value):
    """A CONTROLLER_STARTED whose payload build value is ``value``."""
    kwargs = {"type": EventType.CONTROLLER_STARTED, "payload": {"build": value}}
    if seq is not None:
        kwargs["seq"] = seq
    return Event(**kwargs)


def _started_without_build_key(seq=None):
    kwargs = {"type": EventType.CONTROLLER_STARTED, "payload": {}}
    if seq is not None:
        kwargs["seq"] = seq
    return Event(**kwargs)


def _stopped(seq=None):
    kwargs = {"type": EventType.CONTROLLER_STOPPED, "payload": {}}
    if seq is not None:
        kwargs["seq"] = seq
    return Event(**kwargs)


def test_empty_stream_has_no_build():
    assert build_for_seq([], 10) is None


def test_stream_without_started_has_no_build():
    events = [_stopped(1), _stopped(2), _stopped(3)]
    assert build_for_seq(events, 3) is None


def test_single_started_at_or_before_seq_wins():
    build = {"marker": "only"}
    assert build_for_seq([_started(5, build)], 5) == build
    assert build_for_seq([_started(5, build)], 99) == build


def test_started_after_target_seq_is_ignored():
    assert build_for_seq([_started(7, {"marker": "late"})], 6) is None


def test_last_started_at_or_before_seq_wins():
    first = {"marker": "first"}
    second = {"marker": "second"}
    events = [_started(1, first), _stopped(2), _started(3, second), _stopped(4)]
    assert build_for_seq(events, 4) == second
    assert build_for_seq(events, 2) == first


def test_started_without_build_key_resets_to_none():
    events = [_started(1, {"marker": "first"}), _started_without_build_key(2)]
    assert build_for_seq(events, 2) is None


def test_started_with_explicit_none_build_is_none():
    assert build_for_seq([_started(1, None)], 1) is None


def test_unsealed_started_counts_despite_small_target():
    # seq None never triggers the early break, so an unsealed STARTED is
    # attributed even when the target seq is below every sealed seq.
    unsealed = {"marker": "unsealed"}
    events = [_started(None, unsealed), _started(100, {"marker": "sealed"})]
    assert build_for_seq(events, 0) == unsealed


def test_unsealed_non_started_does_not_change_attribution():
    first = {"marker": "first"}
    events = [_started(1, first), _stopped(None)]
    assert build_for_seq(events, 5) == first


def test_generator_input_works():
    build = {"marker": "gen"}
    events = iter([_started(2, build), _stopped(3)])
    assert build_for_seq(events, 3) == build


def test_target_before_any_started_is_none():
    assert build_for_seq([_started(5, {"marker": "future"})], 4) is None
