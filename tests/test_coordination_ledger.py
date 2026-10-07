from scripts.coordination_ledger import (
    CoordinationEvent, EventType, MissionStatus, AgentID, HostID, CoordinationReducer
)
import datetime

def test_coordination_reducer():
    reducer = CoordinationReducer()
    
    e1 = CoordinationEvent(
        event_id="e1",
        mission_id="m1",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=[],
        head="sha1",
        evidence_ref="issue/1#issuecomment-123",
        created_at="2026-10-07T12:00:00Z",
        payload_hash="hash1"
    )
    
    reducer.apply(e1)
    
    mission = reducer.get_mission("m1")
    assert mission["status"] == MissionStatus.WORKING
    
    e2 = CoordinationEvent(
        event_id="e2",
        mission_id="m1",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.PARTIAL,
        status=MissionStatus.WORKING,
        depends_on=[],
        head="sha2",
        evidence_ref="issue/1#issuecomment-124",
        created_at="2026-10-07T12:05:00Z",
        payload_hash="hash2"
    )
    
    reducer.apply(e2)
    mission = reducer.get_mission("m1")
    assert mission["status"] == MissionStatus.WORKING
    assert mission["head"] == "sha2"
    
    e3 = CoordinationEvent(
        event_id="e3",
        mission_id="m1",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=[],
        head="sha3",
        evidence_ref="issue/1#issuecomment-125",
        created_at="2026-10-07T12:10:00Z",
        payload_hash="hash3"
    )
    
    reducer.apply(e3)
    mission = reducer.get_mission("m1")
    assert mission["status"] == MissionStatus.DONE
    assert mission["head"] == "sha3"
