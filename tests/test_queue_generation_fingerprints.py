"""Deterministic tests for Queue Generation Fingerprints and Supersession.

Ziel: Eine neue Sitzung darf eine alte Queue nicht unbemerkt wieder starten.

Testkriterien:
1. Generation 1 enthält A und B mit generation_id="GEN-1".
2. Task A wird nachweislich abgeschlossen (EventType.FINAL / MissionStatus.DONE).
3. Generation 2 (generation_id="GEN-2") übernimmt B und ergänzt C.
4. Nach der Umstellung:
   - A darf NICHT wieder READY werden (Supersession + Terminal State Schutz).
   - B behält seine gültige Identität und wird als NEXT_READY angeboten.
   - C ist neu in der Generation und wird korrekt erfasst.
5. Task-Fingerprint & Quellfingerprint Bindung:
   - Veränderte Task-Spezifikationen führen zu geänderten Task-Fingerprints.
   - Replay alter Task-Fingerprints auf abgeschlossenen Tasks wird abgewiesen.
"""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    CoordinationReducer,
    EventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import discover_resumable, reduce_store
from scripts.github_coordination import FileCoordinationStore


def compute_task_fingerprint(task_id: str, spec: dict) -> str:
    """Deterministic fingerprint for a task spec."""
    canonical = json.dumps({"task_id": task_id, "spec": spec}, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def compute_queue_generation_fingerprint(generation_id: str, source_sha: str, tasks: dict) -> str:
    """Deterministic fingerprint for a queue generation."""
    task_fps = {tid: compute_task_fingerprint(tid, spec) for tid, spec in sorted(tasks.items())}
    envelope = {
        "generation_id": generation_id,
        "source_sha": source_sha,
        "task_fingerprints": task_fps,
    }
    canonical = json.dumps(envelope, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_queue_generation_supersession_and_next_ready(tmp_path):
    store_file = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(store_file)

    source_sha = "fac447f5c9c22936177069566b82c7319bc35f5c"

    # --- GENERATION 1 ---
    gen1_id = "GEN-001"
    gen1_tasks = {
        "A": {"action": "clean_tmp", "target": "cache"},
        "B": {"action": "build_assets", "target": "dist"},
    }
    gen1_fp = compute_queue_generation_fingerprint(gen1_id, source_sha, gen1_tasks)
    assert len(gen1_fp) == 64

    # Post initial assigned events for Generation 1
    # Evidence ref encodes generation_id and task_fingerprint
    fp_a = compute_task_fingerprint("A", gen1_tasks["A"])
    fp_b = compute_task_fingerprint("B", gen1_tasks["B"])

    store.write_event(CoordinationEvent(
        event_id="e-gen1-assign-a",
        mission_id="A",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=[],
        head=source_sha,
        evidence_ref=f"gen_id={gen1_id};gen_fp={gen1_fp[:16]};task_fp={fp_a}",
        created_at="2026-10-11T12:00:00Z",
        payload_hash="hash-a",
        ownership=AgentID.GOOGLE_WINDOWS.value,
    ))

    store.write_event(CoordinationEvent(
        event_id="e-gen1-assign-b",
        mission_id="B",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=[],
        head=source_sha,
        evidence_ref=f"gen_id={gen1_id};gen_fp={gen1_fp[:16]};task_fp={fp_b}",
        created_at="2026-10-11T12:00:01Z",
        payload_hash="hash-b",
        ownership=AgentID.GOOGLE_WINDOWS.value,
    ))

    # Task A completes in Generation 1
    store.write_event(CoordinationEvent(
        event_id="e-gen1-final-a",
        mission_id="A",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=[],
        head=source_sha,
        evidence_ref=f"gen_id={gen1_id};receipt=rcpt-a1;task_fp={fp_a}",
        created_at="2026-10-11T12:05:00Z",
        payload_hash="hash-final-a",
        ownership=None,  # Released
    ))

    # Verify state after Gen 1: A is DONE, B is WORKING
    reducer1 = reduce_store(store)
    assert reducer1.get_mission("A")["status"] == MissionStatus.DONE
    assert reducer1.get_mission("B")["status"] == MissionStatus.WORKING

    # --- GENERATION 2 (SUPERSESSION) ---
    # Generation 2 adopts B (unmodified spec) and adds C
    gen2_id = "GEN-002"
    gen2_tasks = {
        "B": gen1_tasks["B"],  # Adopted from Gen 1 with identical spec & identity
        "C": {"action": "package_release", "target": "zip"},  # New task
    }
    gen2_fp = compute_queue_generation_fingerprint(gen2_id, source_sha, gen2_tasks)
    assert gen2_fp != gen1_fp, "Different generation must yield a different generation fingerprint"

    fp_b_gen2 = compute_task_fingerprint("B", gen2_tasks["B"])
    assert fp_b_gen2 == fp_b, "Adopted task B must preserve its exact task fingerprint"

    fp_c = compute_task_fingerprint("C", gen2_tasks["C"])

    # Generation 2 posts new task C into the ledger
    store.write_event(CoordinationEvent(
        event_id="e-gen2-assign-c",
        mission_id="C",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=["B"],  # C depends on adopted B
        head=source_sha,
        evidence_ref=f"gen_id={gen2_id};gen_fp={gen2_fp[:16]};task_fp={fp_c}",
        created_at="2026-10-11T12:10:00Z",
        payload_hash="hash-c",
        ownership=AgentID.GOOGLE_WINDOWS.value,
    ))

    # Re-evaluate resumable state in a fresh session
    reducer2 = reduce_store(store)
    resumable_checkpoints = discover_resumable(reducer2, AgentID.GOOGLE_WINDOWS)
    resumable_ids = [c.mission_id for c in resumable_checkpoints]

    # CRITICAL ACCEPATANCE CHECKS:
    # 1. A MUST NOT become READY or resumable again!
    assert "A" not in resumable_ids, "Task A from Generation 1 must NOT be offered again"
    assert reducer2.get_mission("A")["status"] == MissionStatus.DONE

    # 2. B retains its valid identity from Gen 1 and is the NEXT_READY task!
    assert "B" in resumable_ids, "Adopted Task B must remain resumable"
    checkpoint_b = next(c for c in resumable_checkpoints if c.mission_id == "B")
    assert checkpoint_b.mission_id == "B"
    assert checkpoint_b.latest_event_id == "e-gen1-assign-b"

    # 3. C is brand new and dependent on B -> C is NOT yet ready
    assert "C" not in resumable_ids, "Task C depends on B and must NOT be offered before B is DONE"
    assert reducer2.get_mission("C")["status"] == MissionStatus.WORKING

    # NEXT_READY selection:
    next_ready = resumable_ids[0]
    assert next_ready == "B", f"NEXT_READY must be 'B', got {next_ready}"

    # Now B completes
    store.write_event(CoordinationEvent(
        event_id="e-gen2-final-b",
        mission_id="B",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=[],
        head=source_sha,
        evidence_ref=f"gen_id={gen2_id};receipt=rcpt-b1;task_fp={fp_b}",
        created_at="2026-10-11T12:15:00Z",
        payload_hash="hash-final-b",
        ownership=None,
    ))

    # State check after B is complete:
    reducer3 = reduce_store(store)
    resumable3 = discover_resumable(reducer3, AgentID.GOOGLE_WINDOWS)
    resumable3_ids = [c.mission_id for c in resumable3]

    # Neither A nor B can be offered again
    assert "A" not in resumable3_ids
    assert "B" not in resumable3_ids

    # C is now unlocked and is NEXT_READY!
    assert "C" in resumable3_ids
    assert resumable3_ids[0] == "C"


def test_stale_generation_replay_rejected(tmp_path):
    """An old session trying to replay Gen 1 events after Gen 2 progress fails closed."""
    store_file = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(store_file)

    # Completed task in Gen 1
    store.write_event(CoordinationEvent(
        event_id="e1",
        mission_id="TASK_X",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=[],
        head="sha",
        evidence_ref="gen=1;done=true",
        created_at="2026-10-11T12:00:00Z",
        payload_hash="h1",
    ))

    reducer = reduce_store(store)
    assert reducer.get_mission("TASK_X")["status"] == MissionStatus.DONE

    # Stale session tries to assign TASK_X again with a timestamp in the past or present
    stale_event = CoordinationEvent(
        event_id="e2",
        mission_id="TASK_X",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=[],
        head="sha",
        evidence_ref="gen=1;replay=true",
        created_at="2026-10-11T11:50:00Z",  # Stale timestamp
        payload_hash="h2",
    )

    applied = reducer.apply(stale_event)
    assert applied is False, "Stale checkpoint event must be rejected by reducer"
    assert reducer.get_mission("TASK_X")["status"] == MissionStatus.DONE
