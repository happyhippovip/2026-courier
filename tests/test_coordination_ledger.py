from scripts.coordination_ledger import (
    CoordinationEvent, EventType, MissionStatus, AgentID, HostID, CoordinationReducer
)
import datetime

def create_event(eid, mid, etype, status, created_at, agent=AgentID.GOOGLE_WINDOWS, host=HostID.WINDOWS_REMOTE, deps=None, owner=None):
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=agent,
        host_id=host,
        event_type=etype,
        status=status,
        depends_on=deps or [],
        head="sha",
        evidence_ref="ref",
        created_at=created_at,
        payload_hash="hash",
        ownership=owner
    )

def test_coordination_reducer():
    reducer = CoordinationReducer()
    
    e1 = create_event("e1", "m1", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z")
    reducer.apply(e1)
    
    mission = reducer.get_mission("m1")
    assert mission["status"] == MissionStatus.WORKING
    
    # 3. PARTIAL checkpoint remains resumable
    e2 = create_event("e2", "m1", EventType.PARTIAL, MissionStatus.WORKING, "2026-10-07T12:05:00Z")
    reducer.apply(e2)
    mission = reducer.get_mission("m1")
    assert mission["status"] == MissionStatus.WORKING
    
    e3 = create_event("e3", "m1", EventType.FINAL, MissionStatus.DONE, "2026-10-07T12:10:00Z")
    reducer.apply(e3)
    mission = reducer.get_mission("m1")
    assert mission["status"] == MissionStatus.DONE
    assert mission["ownership"] is None # ownership released

def test_replay_protection():
    # 4. duplicate/replayed event has no duplicate effect
    reducer = CoordinationReducer()
    e1 = create_event("1", "m1", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z")
    reducer.apply(e1)
    assert len(reducer.events) == 1
    
    # Replay
    reducer.apply(e1)
    assert len(reducer.events) == 1 # still 1!

def test_stale_checkpoint_ignored():
    # 5. stale checkpoint cannot overwrite newer progress.
    reducer = CoordinationReducer()
    e1 = create_event("1", "m1", EventType.FINAL, MissionStatus.DONE, "2026-10-07T12:10:00Z")
    reducer.apply(e1)
    
    e2_stale = create_event("2", "m1", EventType.PARTIAL, MissionStatus.WORKING, "2026-10-07T12:05:00Z")
    reducer.apply(e2_stale)
    
    mission = reducer.get_mission("m1")
    assert mission["status"] == MissionStatus.DONE

def test_conflicting_ownership():
    # 6. conflicting writer ownership fails safely.
    reducer = CoordinationReducer()
    e1 = create_event("1", "m1", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z", owner="AGENT_A")
    reducer.apply(e1)
    
    # AGENT_B tries to send PARTIAL
    e2 = create_event("2", "m1", EventType.PARTIAL, MissionStatus.WORKING, "2026-10-07T12:05:00Z", owner="AGENT_B")
    reducer.apply(e2)
    
    mission = reducer.get_mission("m1")
    assert mission["latest_event_id"] == "1" # Event 2 rejected

def test_unknown_authority():
    # 9. unknown authority fails closed
    reducer = CoordinationReducer()
    e1 = create_event("1", "m1", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z", agent=AgentID.UNKNOWN)
    reducer.apply(e1)
    
    assert reducer.get_mission("m1") is None


def test_muse_agent_ids_supported():
    reducer = CoordinationReducer()
    e1 = create_event("1", "m1", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z", agent=AgentID.MUSE_MAC, host=HostID.MAC_LOCAL)
    reducer.apply(e1)
    m = reducer.get_mission("m1")
    assert m is not None
    assert m["agent_id"] == AgentID.MUSE_MAC
    assert m["status"] == MissionStatus.WORKING

    e2 = create_event("2", "m2", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z", agent=AgentID.MUSE_WINDOWS, host=HostID.WINDOWS_REMOTE)
    reducer.apply(e2)
    m2 = reducer.get_mission("m2")
    assert m2 is not None
    assert m2["agent_id"] == AgentID.MUSE_WINDOWS

