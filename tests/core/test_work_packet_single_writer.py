"""One host-pressure park/wake cycle must not create a second CURRENT writer."""

import random

import pytest

from courier_core.work_packet import PacketQueue, PacketState, WorkPacket


def _add(queue, packet_id, state, sha="sha1"):
    queue.add_packet(WorkPacket(packet_id, packet_id, sha, state))


def _current_ids(queue):
    return [packet.id for packet in queue.packets.values() if packet.state == PacketState.CURRENT]


def test_work_packet_stays_frozen():
    packet = WorkPacket("p1", "w1", "sha1", PacketState.CURRENT, parked_from=PacketState.NEXT)
    with pytest.raises(AttributeError):
        packet.state = PacketState.PARKED_BY_HOST


def test_unsafe_then_safe_keeps_the_original_writer_only():
    queue = PacketQueue()
    _add(queue, "p1", PacketState.CURRENT)
    _add(queue, "p2", PacketState.NEXT)
    _add(queue, "p3", PacketState.AFTER_NEXT)

    queue.get_admissible_packet("sha1", host_safe=False)
    admissible = queue.get_admissible_packet("sha1", host_safe=True)

    assert admissible is not None
    assert admissible.id == "p1"
    assert admissible.state == PacketState.CURRENT
    assert queue.packets["p1"].state == PacketState.CURRENT
    assert queue.packets["p2"].state == PacketState.NEXT
    assert queue.packets["p3"].state == PacketState.AFTER_NEXT
    assert _current_ids(queue) == ["p1"]


def test_waiting_for_evidence_survives_park_and_wake():
    queue = PacketQueue()
    _add(queue, "p1", PacketState.WAITING_FOR_EVIDENCE)

    queue.get_admissible_packet("sha1", host_safe=False)
    assert queue.packets["p1"].state == PacketState.PARKED_BY_HOST
    assert queue.packets["p1"].parked_from == PacketState.WAITING_FOR_EVIDENCE

    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert queue.packets["p1"].state == PacketState.WAITING_FOR_EVIDENCE
    assert queue.packets["p1"].state != PacketState.CURRENT
    assert admissible is None


def test_sha_move_while_parked_supersedes_and_never_wakes():
    queue = PacketQueue()
    _add(queue, "p1", PacketState.CURRENT)

    queue.get_admissible_packet("sha1", host_safe=False)
    assert queue.packets["p1"].state == PacketState.PARKED_BY_HOST

    admissible = queue.get_admissible_packet("sha2", host_safe=True)
    assert queue.packets["p1"].state == PacketState.SUPERSEDED
    assert admissible is None

    # A later safe tick, even on the packet's old SHA, must not resurrect it.
    admissible = queue.get_admissible_packet("sha1", host_safe=True)
    assert queue.packets["p1"].state == PacketState.SUPERSEDED
    assert admissible is None


def test_repeated_unsafe_ticks_do_not_overwrite_pre_park_state():
    queue = PacketQueue()
    _add(queue, "p1", PacketState.CURRENT)
    _add(queue, "p2", PacketState.NEXT)
    _add(queue, "p3", PacketState.AFTER_NEXT)

    queue.get_admissible_packet("sha1", host_safe=False)
    queue.get_admissible_packet("sha1", host_safe=False)

    assert queue.packets["p1"].state == PacketState.PARKED_BY_HOST
    assert queue.packets["p2"].state == PacketState.PARKED_BY_HOST
    assert queue.packets["p3"].state == PacketState.PARKED_BY_HOST
    assert queue.packets["p1"].parked_from == PacketState.CURRENT
    assert queue.packets["p2"].parked_from == PacketState.NEXT
    assert queue.packets["p3"].parked_from == PacketState.AFTER_NEXT


def test_legacy_parked_packets_without_memory_collapse_to_one_current():
    queue = PacketQueue()
    _add(queue, "p1", PacketState.PARKED_BY_HOST)
    _add(queue, "p2", PacketState.PARKED_BY_HOST)
    assert queue.packets["p1"].parked_from is None
    assert queue.packets["p2"].parked_from is None

    admissible = queue.get_admissible_packet("sha1", host_safe=True)

    assert admissible.id == "p1"
    assert queue.packets["p1"].state == PacketState.CURRENT
    assert queue.packets["p2"].state == PacketState.NEXT
    assert _current_ids(queue) == ["p1"]


def test_explicit_safe_unsafe_sequence_keeps_at_most_one_current():
    queue = PacketQueue()
    _add(queue, "p1", PacketState.CURRENT)
    _add(queue, "p2", PacketState.NEXT)
    _add(queue, "p3", PacketState.AFTER_NEXT)
    _add(queue, "p4", PacketState.WAITING_FOR_EVIDENCE)

    for host_safe in (False, True, False, False, True, True, False, True):
        queue.get_admissible_packet("sha1", host_safe=host_safe)
        assert len(_current_ids(queue)) <= 1


@pytest.mark.parametrize("seed", range(5))
def test_seeded_ticks_keep_at_most_one_current(seed):
    rng = random.Random(seed)
    queue = PacketQueue()
    initial = (
        PacketState.CURRENT,
        PacketState.NEXT,
        PacketState.AFTER_NEXT,
        PacketState.WAITING_FOR_EVIDENCE,
        PacketState.PARKED_BY_HOST,
    )
    for index, state in enumerate(initial):
        _add(queue, f"p{index}", state)

    calls = [(False, "sha1"), (True, "sha1")]
    for _ in range(20):
        calls.append((rng.choice((True, False)), rng.choice(("sha1", "sha1", "sha2"))))

    for host_safe, sha in calls:
        queue.get_admissible_packet(sha, host_safe=host_safe)
        assert len(_current_ids(queue)) <= 1
